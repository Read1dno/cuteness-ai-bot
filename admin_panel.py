from fastapi import FastAPI, Request, HTTPException, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import asyncpg
import asyncio
import secrets
import base64
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import os
from pathlib import Path
import hashlib
import uvicorn

from config import DATABASE_URL, ADMIN_USERNAME, ADMIN_PASSWORD

SECRET_KEY = secrets.token_hex(32)

app = FastAPI(title="Cuteness Bot Admin Panel", docs_url=None, redoc_url=None)
security = HTTPBasic()
templates = Jinja2Templates(directory="templates")

_pool: Optional[asyncpg.Pool] = None

async def get_db_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _pool

async def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return credentials.username

def create_templates():
    os.makedirs("templates", exist_ok=True)
    
    main_template = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Cuteness Bot Admin{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        .glass { backdrop-filter: blur(10px); background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); }
        .gradient-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .card-hover:hover { transform: translateY(-4px); transition: all 0.3s ease; }
        .animate-fade-in { animation: fadeIn 0.5s ease-in; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .stat-card { background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%); }
    </style>
</head>
<body class="gradient-bg min-h-screen">
    <nav class="glass sticky top-0 z-50 border-b border-white/20">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between items-center h-16">
                <div class="flex items-center space-x-4">
                    <i class="fas fa-heart text-pink-400 text-2xl"></i>
                    <h1 class="text-xl font-bold text-white">Cuteness Bot Admin</h1>
                </div>
                <div class="flex items-center space-x-4">
                    <div class="text-sm text-white/80">{{ datetime.now().strftime('%H:%M') }}</div>
                </div>
            </div>
        </div>
    </nav>
    
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {% block content %}{% endblock %}
    </main>
    
    <script>
        function updateTime() {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
            const timeEl = document.querySelector('.text-white\\/80');
            if (timeEl) timeEl.textContent = timeStr;
        }
        setInterval(updateTime, 1000);
        
        async function approveImage(imageId) {
            try {
                const response = await fetch(`/api/approve/${imageId}`, { method: 'POST' });
                if (response.ok) location.reload();
            } catch (error) {
                alert('Ошибка при одобрении');
            }
        }
        
        async function banUser(imageId) {
            if (confirm('Забанить пользователя?')) {
                try {
                    const response = await fetch(`/api/ban/${imageId}`, { method: 'POST' });
                    if (response.ok) location.reload();
                } catch (error) {
                    alert('Ошибка при бане');
                }
            }
        }
        
        async function deleteImage(imageId) {
            if (confirm('Удалить изображение?')) {
                try {
                    const response = await fetch(`/api/delete/${imageId}`, { method: 'DELETE' });
                    if (response.ok) location.reload();
                } catch (error) {
                    alert('Ошибка при удалении');
                }
            }
        }
    </script>
</body>
</html>'''

    dashboard_template = '''{% extends "base.html" %}
{% block content %}
<div x-data="dashboard()" class="animate-fade-in">
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div class="stat-card glass rounded-xl p-6 card-hover">
            <div class="flex items-center">
                <div class="p-3 rounded-full bg-blue-500/20">
                    <i class="fas fa-images text-blue-400 text-xl"></i>
                </div>
                <div class="ml-4">
                    <p class="text-sm font-medium text-white/70">Всего изображений</p>
                    <p class="text-2xl font-bold text-white">{{ stats.total_images }}</p>
                </div>
            </div>
        </div>
        
        <div class="stat-card glass rounded-xl p-6 card-hover">
            <div class="flex items-center">
                <div class="p-3 rounded-full bg-green-500/20">
                    <i class="fas fa-check-circle text-green-400 text-xl"></i>
                </div>
                <div class="ml-4">
                    <p class="text-sm font-medium text-white/70">Одобрено</p>
                    <p class="text-2xl font-bold text-white">{{ stats.approved_images }}</p>
                </div>
            </div>
        </div>
        
        <div class="stat-card glass rounded-xl p-6 card-hover">
            <div class="flex items-center">
                <div class="p-3 rounded-full bg-yellow-500/20">
                    <i class="fas fa-clock text-yellow-400 text-xl"></i>
                </div>
                <div class="ml-4">
                    <p class="text-sm font-medium text-white/70">На модерации</p>
                    <p class="text-2xl font-bold text-white">{{ stats.pending_images }}</p>
                </div>
            </div>
        </div>
        
        <div class="stat-card glass rounded-xl p-6 card-hover">
            <div class="flex items-center">
                <div class="p-3 rounded-full bg-purple-500/20">
                    <i class="fas fa-users text-purple-400 text-xl"></i>
                </div>
                <div class="ml-4">
                    <p class="text-sm font-medium text-white/70">Пользователей</p>
                    <p class="text-2xl font-bold text-white">{{ stats.total_users }}</p>
                </div>
            </div>
        </div>
    </div>
    
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="lg:col-span-2">
            <div class="glass rounded-xl p-6">
                <div class="flex items-center justify-between mb-6">
                    <h2 class="text-xl font-bold text-white flex items-center">
                        <i class="fas fa-gavel mr-3 text-amber-400"></i>
                        Модерация
                    </h2>
                    <button @click="refreshData" class="px-4 py-2 bg-blue-500/20 hover:bg-blue-500/30 rounded-lg text-white transition-colors">
                        <i class="fas fa-sync-alt mr-2"></i>Обновить
                    </button>
                </div>
                
                <div class="space-y-4">
                    {% for image in pending_images %}
                    <div class="glass rounded-lg p-4 flex items-center space-x-4">
                        <div class="w-16 h-16 bg-gray-700 rounded-lg flex items-center justify-center">
                            <i class="fas fa-image text-gray-400"></i>
                        </div>
                        <div class="flex-1">
                            <div class="flex items-center space-x-2">
                                <span class="font-medium text-white">{{ image.username or 'Аноним' }}</span>
                                <span class="text-xs text-white/60">ID: {{ image.user_id }}</span>
                            </div>
                            <div class="text-sm text-white/70 mt-1">
                                Оценка: {{ "%.2f"|format(image.raw_score) }}% | {{ image.created_at.strftime('%d.%m.%Y %H:%M') }}
                            </div>
                        </div>
                        <div class="flex space-x-2">
                            <button onclick="approveImage({{ image.id }})" class="px-3 py-1 bg-green-500/20 hover:bg-green-500/40 text-green-400 rounded-md transition-colors text-sm">
                                <i class="fas fa-check mr-1"></i>Одобрить
                            </button>
                            <button onclick="banUser({{ image.id }})" class="px-3 py-1 bg-red-500/20 hover:bg-red-500/40 text-red-400 rounded-md transition-colors text-sm">
                                <i class="fas fa-ban mr-1"></i>Забанить
                            </button>
                        </div>
                    </div>
                    {% endfor %}
                    
                    {% if not pending_images %}
                    <div class="text-center py-8 text-white/60">
                        <i class="fas fa-check-circle text-4xl mb-3"></i>
                        <p>Нет изображений на модерации</p>
                    </div>
                    {% endif %}
                </div>
            </div>
        </div>
        
        <div>
            <div class="glass rounded-xl p-6 mb-6">
                <h3 class="text-lg font-bold text-white mb-4 flex items-center">
                    <i class="fas fa-trophy mr-3 text-yellow-400"></i>
                    Топ изображений
                </h3>
                <div class="space-y-3">
                    {% for image in top_images[:5] %}
                    <div class="flex items-center justify-between">
                        <div class="flex items-center space-x-3">
                            <div class="w-8 h-8 rounded-full bg-gradient-to-r from-yellow-400 to-orange-500 flex items-center justify-center text-white font-bold text-sm">
                                {{ loop.index }}
                            </div>
                            <div>
                                <div class="text-white text-sm font-medium">{{ image.username or 'Аноним' }}</div>
                                <div class="text-white/60 text-xs">{{ "%.2f"|format(image.raw_score) }}%</div>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            
            <div class="glass rounded-xl p-6">
                <h3 class="text-lg font-bold text-white mb-4 flex items-center">
                    <i class="fas fa-chart-line mr-3 text-green-400"></i>
                    Активность
                </h3>
                <div class="space-y-3">
                    <div class="flex justify-between">
                        <span class="text-white/70">Сегодня</span>
                        <span class="text-white font-medium">{{ stats.today_images }}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-white/70">За неделю</span>
                        <span class="text-white font-medium">{{ stats.week_images }}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-white/70">За месяц</span>
                        <span class="text-white font-medium">{{ stats.month_images }}</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
function dashboard() {
    return {
        refreshData() {
            location.reload();
        }
    }
}
</script>
{% endblock %}'''

    users_template = '''{% extends "base.html" %}
{% block content %}
<div class="animate-fade-in">
    <div class="glass rounded-xl p-6 mb-6">
        <div class="flex items-center justify-between mb-6">
            <h2 class="text-xl font-bold text-white flex items-center">
                <i class="fas fa-users mr-3 text-blue-400"></i>
                Пользователи ({{ users|length }})
            </h2>
            <div class="flex space-x-4">
                <input type="text" placeholder="Поиск..." class="px-4 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/50 focus:outline-none focus:border-white/40" id="userSearch">
                <select class="px-4 py-2 bg-white/10 border border-white/20 rounded-lg text-white focus:outline-none focus:border-white/40" id="statusFilter">
                    <option value="">Все статусы</option>
                    <option value="active">Активные</option>
                    <option value="banned">Заблокированные</option>
                    <option value="warned">С предупреждениями</option>
                </select>
            </div>
        </div>
        
        <div class="overflow-x-auto">
            <table class="w-full">
                <thead>
                    <tr class="border-b border-white/10">
                        <th class="text-left py-3 px-4 font-medium text-white/70">Пользователь</th>
                        <th class="text-left py-3 px-4 font-medium text-white/70">Изображений</th>
                        <th class="text-left py-3 px-4 font-medium text-white/70">Лучший результат</th>
                        <th class="text-left py-3 px-4 font-medium text-white/70">Предупреждения</th>
                        <th class="text-left py-3 px-4 font-medium text-white/70">Статус</th>
                        <th class="text-left py-3 px-4 font-medium text-white/70">Действия</th>
                    </tr>
                </thead>
                <tbody>
                    {% for user in users %}
                    <tr class="border-b border-white/5 hover:bg-white/5">
                        <td class="py-3 px-4">
                            <div class="flex items-center space-x-3">
                                <div class="w-10 h-10 bg-gradient-to-r from-blue-400 to-purple-500 rounded-full flex items-center justify-center text-white font-bold">
                                    {{ user.username[0].upper() if user.username else 'A' }}
                                </div>
                                <div>
                                    <div class="font-medium text-white">{{ user.username or 'Аноним' }}</div>
                                    <div class="text-sm text-white/60">ID: {{ user.user_id }}</div>
                                </div>
                            </div>
                        </td>
                        <td class="py-3 px-4 text-white">{{ user.image_count }}</td>
                        <td class="py-3 px-4 text-white">{{ "%.2f"|format(user.best_score) if user.best_score else '-' }}%</td>
                        <td class="py-3 px-4">
                            <span class="px-2 py-1 rounded-full text-xs {% if user.warnings == 0 %}bg-green-500/20 text-green-400{% elif user.warnings < 3 %}bg-yellow-500/20 text-yellow-400{% else %}bg-red-500/20 text-red-400{% endif %}">
                                {{ user.warnings }}
                            </span>
                        </td>
                        <td class="py-3 px-4">
                            {% if user.banned %}
                            <span class="px-2 py-1 bg-red-500/20 text-red-400 rounded-full text-xs">Заблокирован</span>
                            {% else %}
                            <span class="px-2 py-1 bg-green-500/20 text-green-400 rounded-full text-xs">Активен</span>
                            {% endif %}
                        </td>
                        <td class="py-3 px-4">
                            <div class="flex space-x-2">
                                {% if not user.banned %}
                                <button onclick="banUserById({{ user.user_id }})" class="px-3 py-1 bg-red-500/20 hover:bg-red-500/40 text-red-400 rounded-md text-xs">
                                    Заблокировать
                                </button>
                                {% else %}
                                <button onclick="unbanUser({{ user.user_id }})" class="px-3 py-1 bg-green-500/20 hover:bg-green-500/40 text-green-400 rounded-md text-xs">
                                    Разблокировать
                                </button>
                                {% endif %}
                                <button onclick="viewUserImages({{ user.user_id }})" class="px-3 py-1 bg-blue-500/20 hover:bg-blue-500/40 text-blue-400 rounded-md text-xs">
                                    Изображения
                                </button>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<script>
async function banUserById(userId) {
    if (confirm('Заблокировать пользователя?')) {
        try {
            const response = await fetch(`/api/ban-user/${userId}`, { method: 'POST' });
            if (response.ok) location.reload();
        } catch (error) {
            alert('Ошибка при блокировке');
        }
    }
}

async function unbanUser(userId) {
    if (confirm('Разблокировать пользователя?')) {
        try {
            const response = await fetch(`/api/unban-user/${userId}`, { method: 'POST' });
            if (response.ok) location.reload();
        } catch (error) {
            alert('Ошибка при разблокировке');
        }
    }
}

function viewUserImages(userId) {
    window.open(`/user/${userId}`, '_blank');
}

document.getElementById('userSearch').addEventListener('input', filterUsers);
document.getElementById('statusFilter').addEventListener('change', filterUsers);

function filterUsers() {
    const searchTerm = document.getElementById('userSearch').value.toLowerCase();
    const statusFilter = document.getElementById('statusFilter').value;
    const rows = document.querySelectorAll('tbody tr');
    
    rows.forEach(row => {
        const username = row.querySelector('td:first-child').textContent.toLowerCase();
        const status = row.querySelector('td:nth-child(5) span').textContent.toLowerCase();
        
        let showRow = true;
        
        if (searchTerm && !username.includes(searchTerm)) {
            showRow = false;
        }
        
        if (statusFilter) {
            if (statusFilter === 'banned' && !status.includes('заблокирован')) showRow = false;
            if (statusFilter === 'active' && !status.includes('активен')) showRow = false;
            if (statusFilter === 'warned' && !row.querySelector('td:nth-child(4) span').textContent.includes('0')) showRow = false;
        }
        
        row.style.display = showRow ? '' : 'none';
    });
}
</script>
{% endblock %}'''

    with open("templates/base.html", "w", encoding="utf-8") as f:
        f.write(main_template)
    with open("templates/dashboard.html", "w", encoding="utf-8") as f:
        f.write(dashboard_template)
    with open("templates/users.html", "w", encoding="utf-8") as f:
        f.write(users_template)

create_templates()

@app.on_event("startup")
async def startup_event():
    await get_db_pool()

@app.on_event("shutdown")
async def shutdown_event():
    global _pool
    if _pool:
        await _pool.close()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: str = Depends(authenticate)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        stats = {}
        stats['total_images'] = await conn.fetchval("SELECT COUNT(*) FROM images")
        stats['approved_images'] = await conn.fetchval("SELECT COUNT(*) FROM images WHERE approved = 1")
        stats['pending_images'] = await conn.fetchval("SELECT COUNT(*) FROM images WHERE approved = 0")
        stats['total_users'] = await conn.fetchval("SELECT COUNT(DISTINCT user_id) FROM images")
        stats['today_images'] = await conn.fetchval("SELECT COUNT(*) FROM images WHERE DATE(created_at) = CURRENT_DATE")
        stats['week_images'] = await conn.fetchval("SELECT COUNT(*) FROM images WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'")
        stats['month_images'] = await conn.fetchval("SELECT COUNT(*) FROM images WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'")
        
        pending_images = await conn.fetch("""
            SELECT id, user_id, username, raw_score, created_at
            FROM images 
            WHERE approved = 0 AND raw_score > 85
            ORDER BY created_at DESC 
            LIMIT 20
        """)
        
        top_images = await conn.fetch("""
            SELECT username, raw_score, user_id
            FROM images 
            WHERE approved = 1 AND nsfw = 0
            ORDER BY raw_score DESC 
            LIMIT 10
        """)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats,
        "pending_images": pending_images,
        "top_images": top_images,
        "datetime": datetime
    })

@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, user: str = Depends(authenticate)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        users_data = await conn.fetch("""
            SELECT 
                i.user_id,
                i.username,
                COUNT(i.id) as image_count,
                MAX(i.raw_score) as best_score,
                COALESCE(w.warnings, 0) as warnings,
                COALESCE(w.banned, 0) as banned
            FROM images i
            LEFT JOIN user_warnings w ON i.user_id = w.user_id
            GROUP BY i.user_id, i.username, w.warnings, w.banned
            ORDER BY image_count DESC
        """)
    
    return templates.TemplateResponse("users.html", {
        "request": request,
        "users": users_data
    })

@app.get("/images", response_class=HTMLResponse)
async def images_page(request: Request, user: str = Depends(authenticate)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        images = await conn.fetch("""
            SELECT id, user_id, username, raw_score, approved, nsfw, created_at
            FROM images 
            ORDER BY created_at DESC 
            LIMIT 100
        """)
    
    return templates.TemplateResponse("images.html", {
        "request": request,
        "images": images
    })

@app.post("/api/approve/{image_id}")
async def approve_image(image_id: int, user: str = Depends(authenticate)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE images SET approved = 1 WHERE id = $1", image_id)
    return {"status": "success"}

@app.post("/api/ban/{image_id}")
async def ban_image(image_id: int, user: str = Depends(authenticate)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user_id = await conn.fetchval("SELECT user_id FROM images WHERE id = $1", image_id)
        if user_id:
            await conn.execute("UPDATE images SET approved = 0 WHERE id = $1", image_id)
            await conn.execute("""
                INSERT INTO user_warnings (user_id, warnings, banned) 
                VALUES ($1, 1, 1) 
                ON CONFLICT (user_id) 
                DO UPDATE SET warnings = user_warnings.warnings + 1, banned = 1
            """, user_id)
    return {"status": "success"}

@app.delete("/api/delete/{image_id}")
async def delete_image(image_id: int, user: str = Depends(authenticate)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM images WHERE id = $1", image_id)
    return {"status": "success"}

@app.post("/api/ban-user/{user_id}")
async def ban_user_by_id(user_id: int, user: str = Depends(authenticate)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO user_warnings (user_id, warnings, banned) 
            VALUES ($1, 1, 1) 
            ON CONFLICT (user_id) 
            DO UPDATE SET banned = 1
        """, user_id)
    return {"status": "success"}

@app.post("/api/unban-user/{user_id}")
async def unban_user(user_id: int, user: str = Depends(authenticate)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO user_warnings (user_id, warnings, banned) 
            VALUES ($1, 0, 0) 
            ON CONFLICT (user_id) 
            DO UPDATE SET banned = 0
        """, user_id)
    return {"status": "success"}

@app.get("/api/stats")
async def get_stats(user: str = Depends(authenticate)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        total_images = await conn.fetchval("SELECT COUNT(*) FROM images")
        approved_images = await conn.fetchval("SELECT COUNT(*) FROM images WHERE approved = 1")
        pending_images = await conn.fetchval("SELECT COUNT(*) FROM images WHERE approved = 0")
        total_users = await conn.fetchval("SELECT COUNT(DISTINCT user_id) FROM images")
        banned_users = await conn.fetchval("SELECT COUNT(*) FROM user_warnings WHERE banned = 1")
        
        daily_stats = await conn.fetch("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM images 
            WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY date
        """)
        
        top_scores = await conn.fetch("""
            SELECT raw_score, COUNT(*) as count
            FROM images 
            WHERE approved = 1
            GROUP BY CASE 
                WHEN raw_score >= 90 THEN '90+'
                WHEN raw_score >= 80 THEN '80-89'
                WHEN raw_score >= 70 THEN '70-79'
                WHEN raw_score >= 60 THEN '60-69'
                ELSE '0-59'
            END
            ORDER BY raw_score DESC
        """)
    
    return {
        "total_images": total_images,
        "approved_images": approved_images,
        "pending_images": pending_images,
        "total_users": total_users,
        "banned_users": banned_users,
        "daily_stats": [{"date": str(row["date"]), "count": row["count"]} for row in daily_stats],
        "score_distribution": [{"range": row["raw_score"], "count": row["count"]} for row in top_scores]
    }

@app.get("/user/{user_id}", response_class=HTMLResponse)
async def user_detail(request: Request, user_id: int, user: str = Depends(authenticate)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user_info = await conn.fetchrow("""
            SELECT DISTINCT user_id, username FROM images WHERE user_id = $1 LIMIT 1
        """, user_id)
        
        user_images = await conn.fetch("""
            SELECT id, raw_score, approved, nsfw, created_at, filename
            FROM images 
            WHERE user_id = $1 
            ORDER BY created_at DESC
        """, user_id)
        
        warnings_info = await conn.fetchrow("""
            SELECT warnings, banned FROM user_warnings WHERE user_id = $1
        """, user_id)
    
    user_detail_template = '''{% extends "base.html" %}
{% block content %}
<div class="animate-fade-in">
    <div class="glass rounded-xl p-6 mb-6">
        <div class="flex items-center justify-between mb-6">
            <div class="flex items-center space-x-4">
                <div class="w-16 h-16 bg-gradient-to-r from-blue-400 to-purple-500 rounded-full flex items-center justify-center text-white font-bold text-2xl">
                    {{ (user_info.username[0].upper() if user_info.username else 'A') }}
                </div>
                <div>
                    <h2 class="text-2xl font-bold text-white">{{ user_info.username or 'Аноним' }}</h2>
                    <p class="text-white/60">ID: {{ user_info.user_id }}</p>
                    {% if warnings_info %}
                    <div class="flex items-center space-x-2 mt-2">
                        <span class="px-2 py-1 rounded-full text-xs {% if warnings_info.banned %}bg-red-500/20 text-red-400{% else %}bg-green-500/20 text-green-400{% endif %}">
                            {% if warnings_info.banned %}Заблокирован{% else %}Активен{% endif %}
                        </span>
                        <span class="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded-full text-xs">
                            Предупреждений: {{ warnings_info.warnings }}
                        </span>
                    </div>
                    {% endif %}
                </div>
            </div>
            <a href="/users" class="px-4 py-2 bg-blue-500/20 hover:bg-blue-500/30 rounded-lg text-white transition-colors">
                <i class="fas fa-arrow-left mr-2"></i>Назад к списку
            </a>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <div class="stat-card glass rounded-lg p-4">
                <div class="text-2xl font-bold text-white">{{ user_images|length }}</div>
                <div class="text-white/60">Всего изображений</div>
            </div>
            <div class="stat-card glass rounded-lg p-4">
                <div class="text-2xl font-bold text-green-400">{{ user_images|selectattr("approved", "equalto", 1)|list|length }}</div>
                <div class="text-white/60">Одобрено</div>
            </div>
            <div class="stat-card glass rounded-lg p-4">
                <div class="text-2xl font-bold text-blue-400">{{ "%.2f"|format(user_images|selectattr("approved", "equalto", 1)|map(attribute="raw_score")|max or 0) }}%</div>
                <div class="text-white/60">Лучший результат</div>
            </div>
        </div>
        
        <h3 class="text-xl font-bold text-white mb-4">Изображения пользователя</h3>
        <div class="overflow-x-auto">
            <table class="w-full">
                <thead>
                    <tr class="border-b border-white/10">
                        <th class="text-left py-3 px-4 font-medium text-white/70">ID</th>
                        <th class="text-left py-3 px-4 font-medium text-white/70">Оценка</th>
                        <th class="text-left py-3 px-4 font-medium text-white/70">Статус</th>
                        <th class="text-left py-3 px-4 font-medium text-white/70">Дата</th>
                        <th class="text-left py-3 px-4 font-medium text-white/70">Действия</th>
                    </tr>
                </thead>
                <tbody>
                    {% for image in user_images %}
                    <tr class="border-b border-white/5 hover:bg-white/5">
                        <td class="py-3 px-4 text-white">{{ image.id }}</td>
                        <td class="py-3 px-4 text-white">{{ "%.2f"|format(image.raw_score) }}%</td>
                        <td class="py-3 px-4">
                            <span class="px-2 py-1 rounded-full text-xs {% if image.approved %}bg-green-500/20 text-green-400{% else %}bg-yellow-500/20 text-yellow-400{% endif %}">
                                {% if image.approved %}Одобрено{% else %}На модерации{% endif %}
                            </span>
                            {% if image.nsfw %}
                            <span class="px-2 py-1 bg-red-500/20 text-red-400 rounded-full text-xs ml-1">NSFW</span>
                            {% endif %}
                        </td>
                        <td class="py-3 px-4 text-white/70">{{ image.created_at.strftime('%d.%m.%Y %H:%M') }}</td>
                        <td class="py-3 px-4">
                            <div class="flex space-x-2">
                                {% if not image.approved %}
                                <button onclick="approveImage({{ image.id }})" class="px-2 py-1 bg-green-500/20 hover:bg-green-500/40 text-green-400 rounded text-xs">
                                    Одобрить
                                </button>
                                {% endif %}
                                <button onclick="deleteImage({{ image.id }})" class="px-2 py-1 bg-red-500/20 hover:bg-red-500/40 text-red-400 rounded text-xs">
                                    Удалить
                                </button>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endblock %}'''
    
    if not os.path.exists("templates/user_detail.html"):
        with open("templates/user_detail.html", "w", encoding="utf-8") as f:
            f.write(user_detail_template)
    
    return templates.TemplateResponse("user_detail.html", {
        "request": request,
        "user_info": user_info,
        "user_images": user_images,
        "warnings_info": warnings_info or {"warnings": 0, "banned": False}
    })

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, user: str = Depends(authenticate)):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        daily_stats = await conn.fetch("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM images 
            WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY date
        """)
        
        score_distribution = await conn.fetch("""
            SELECT 
                CASE 
                    WHEN raw_score >= 95 THEN '95-100%'
                    WHEN raw_score >= 90 THEN '90-95%'
                    WHEN raw_score >= 80 THEN '80-90%'
                    WHEN raw_score >= 70 THEN '70-80%'
                    WHEN raw_score >= 60 THEN '60-70%'
                    ELSE '0-60%'
                END as score_range,
                COUNT(*) as count
            FROM images 
            WHERE approved = 1
            GROUP BY 
                CASE 
                    WHEN raw_score >= 95 THEN '95-100%'
                    WHEN raw_score >= 90 THEN '90-95%'
                    WHEN raw_score >= 80 THEN '80-90%'
                    WHEN raw_score >= 70 THEN '70-80%'
                    WHEN raw_score >= 60 THEN '60-70%'
                    ELSE '0-60%'
                END
            ORDER BY MIN(raw_score) DESC
        """)
        
        top_users = await conn.fetch("""
            SELECT username, user_id, COUNT(*) as image_count, AVG(raw_score) as avg_score, MAX(raw_score) as best_score
            FROM images 
            WHERE approved = 1
            GROUP BY username, user_id
            ORDER BY image_count DESC
            LIMIT 10
        """)
    
    analytics_template = '''{% extends "base.html" %}
{% block content %}
<div class="animate-fade-in">
    <div class="mb-8">
        <h2 class="text-2xl font-bold text-white mb-6 flex items-center">
            <i class="fas fa-chart-bar mr-3 text-green-400"></i>
            Аналитика
        </h2>
        
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <div class="glass rounded-xl p-6">
                <h3 class="text-lg font-bold text-white mb-4">Активность за 30 дней</h3>
                <div class="h-64 flex items-end justify-between space-x-1">
                    {% for stat in daily_stats[-30:] %}
                    <div class="flex-1 bg-blue-500/20 hover:bg-blue-500/40 transition-colors rounded-t" 
                         style="height: {{ (stat.count / (daily_stats|map(attribute='count')|max or 1) * 100)|round }}%"
                         title="{{ stat.date }}: {{ stat.count }} изображений">
                    </div>
                    {% endfor %}
                </div>
                <div class="text-center text-white/60 text-sm mt-2">
                    Последние 30 дней
                </div>
            </div>
            
            <div class="glass rounded-xl p-6">
                <h3 class="text-lg font-bold text-white mb-4">Распределение оценок</h3>
                <div class="space-y-3">
                    {% for dist in score_distribution %}
                    <div class="flex items-center justify-between">
                        <span class="text-white/70">{{ dist.score_range }}</span>
                        <div class="flex items-center space-x-3">
                            <div class="w-24 bg-white/10 rounded-full h-2">
                                <div class="bg-gradient-to-r from-green-400 to-blue-500 h-2 rounded-full" 
                                     style="width: {{ (dist.count / (score_distribution|map(attribute='count')|max or 1) * 100)|round }}%"></div>
                            </div>
                            <span class="text-white font-medium w-8">{{ dist.count }}</span>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        
        <div class="glass rounded-xl p-6">
            <h3 class="text-lg font-bold text-white mb-4">Топ пользователей</h3>
            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead>
                        <tr class="border-b border-white/10">
                            <th class="text-left py-3 px-4 font-medium text-white/70">Место</th>
                            <th class="text-left py-3 px-4 font-medium text-white/70">Пользователь</th>
                            <th class="text-left py-3 px-4 font-medium text-white/70">Изображений</th>
                            <th class="text-left py-3 px-4 font-medium text-white/70">Средняя оценка</th>
                            <th class="text-left py-3 px-4 font-medium text-white/70">Лучший результат</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for user in top_users %}
                        <tr class="border-b border-white/5 hover:bg-white/5">
                            <td class="py-3 px-4">
                                <div class="w-8 h-8 rounded-full bg-gradient-to-r from-yellow-400 to-orange-500 flex items-center justify-center text-white font-bold text-sm">
                                    {{ loop.index }}
                                </div>
                            </td>
                            <td class="py-3 px-4 text-white">{{ user.username or 'Аноним' }}</td>
                            <td class="py-3 px-4 text-white">{{ user.image_count }}</td>
                            <td class="py-3 px-4 text-white">{{ "%.1f"|format(user.avg_score) }}%</td>
                            <td class="py-3 px-4 text-white">{{ "%.2f"|format(user.best_score) }}%</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
{% endblock %}'''
    
    if not os.path.exists("templates/analytics.html"):
        with open("templates/analytics.html", "w", encoding="utf-8") as f:
            f.write(analytics_template)
    
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "daily_stats": daily_stats,
        "score_distribution": score_distribution,
        "top_users": top_users
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: str = Depends(authenticate)):
    settings_template = '''{% extends "base.html" %}
{% block content %}
<div class="animate-fade-in">
    <div class="max-w-4xl mx-auto">
        <h2 class="text-2xl font-bold text-white mb-6 flex items-center">
            <i class="fas fa-cog mr-3 text-gray-400"></i>
            Настройки
        </h2>
        
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="glass rounded-xl p-6">
                <h3 class="text-lg font-bold text-white mb-4">Модерация</h3>
                <div class="space-y-4">
                    <div class="flex items-center justify-between">
                        <label class="text-white/70">Автоодобрение при оценке выше</label>
                        <input type="number" value="95" class="px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white w-20">
                    </div>
                    <div class="flex items-center justify-between">
                        <label class="text-white/70">Лимит изображений на модерации</label>
                        <input type="number" value="50" class="px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white w-20">
                    </div>
                    <div class="flex items-center justify-between">
                        <label class="text-white/70">Включить уведомления</label>
                        <input type="checkbox" class="toggle" checked>
                    </div>
                </div>
            </div>
            
            <div class="glass rounded-xl p-6">
                <h3 class="text-lg font-bold text-white mb-4">Безопасность</h3>
                <div class="space-y-4">
                    <div class="flex items-center justify-between">
                        <label class="text-white/70">Автобан за NSFW</label>
                        <input type="checkbox" class="toggle" checked>
                    </div>
                    <div class="flex items-center justify-between">
                        <label class="text-white/70">Предупреждений до бана</label>
                        <input type="number" value="3" class="px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white w-20">
                    </div>
                    <div class="flex items-center justify-between">
                        <label class="text-white/70">Очистка логов (дней)</label>
                        <input type="number" value="30" class="px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white w-20">
                    </div>
                </div>
            </div>
            
            <div class="glass rounded-xl p-6 lg:col-span-2">
                <h3 class="text-lg font-bold text-white mb-4">Система</h3>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <button class="px-4 py-3 bg-blue-500/20 hover:bg-blue-500/40 rounded-lg text-white transition-colors">
                        <i class="fas fa-database mr-2"></i>
                        Очистить кэш
                    </button>
                    <button class="px-4 py-3 bg-green-500/20 hover:bg-green-500/40 rounded-lg text-white transition-colors">
                        <i class="fas fa-download mr-2"></i>
                        Экспорт данных
                    </button>
                    <button class="px-4 py-3 bg-red-500/20 hover:bg-red-500/40 rounded-lg text-white transition-colors">
                        <i class="fas fa-trash mr-2"></i>
                        Очистить старые файлы
                    </button>
                </div>
                
                <div class="mt-6 p-4 bg-white/5 rounded-lg">
                    <h4 class="text-white font-medium mb-2">Информация о системе</h4>
                    <div class="grid grid-cols-2 gap-4 text-sm text-white/70">
                        <div>Версия: 1.0.0</div>
                        <div>Активных подключений: 12</div>
                        <div>Использование памяти: 45%</div>
                        <div>Последнее обновление: Сегодня</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="mt-6 text-center">
            <button class="px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 rounded-lg text-white font-medium transition-all">
                <i class="fas fa-save mr-2"></i>
                Сохранить настройки
            </button>
        </div>
    </div>
</div>

<style>
.toggle {
    appearance: none;
    width: 3rem;
    height: 1.5rem;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 9999px;
    position: relative;
    cursor: pointer;
    outline: none;
    transition: background-color 0.3s;
}

.toggle:checked {
    background: linear-gradient(135deg, #3B82F6, #8B5CF6);
}

.toggle::before {
    content: '';
    position: absolute;
    top: 2px;
    left: 2px;
    width: 1.25rem;
    height: 1.25rem;
    background: white;
    border-radius: 50%;
    transition: transform 0.3s;
}

.toggle:checked::before {
    transform: translateX(1.5rem);
}
</style>
{% endblock %}'''
    
    if not os.path.exists("templates/settings.html"):
        with open("templates/settings.html", "w", encoding="utf-8") as f:
            f.write(settings_template)
    
    return templates.TemplateResponse("settings.html", {"request": request})

if __name__ == "__main__":
    uvicorn.run("admin_panel:app", host="0.0.0.0", port=8000, reload=True)
from fastapi import FastAPI, APIRouter, HTTPException, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import requests
import hashlib
import time
from functools import lru_cache

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Marvel API credentials
MARVEL_PUBLIC_KEY = os.environ['MARVEL_PUBLIC_KEY']
MARVEL_PRIVATE_KEY = os.environ['MARVEL_PRIVATE_KEY']
MARVEL_BASE_URL = "https://gateway.marvel.com/v1/public"

# Create the main app
app = FastAPI(title="Marvel Character Database")
api_router = APIRouter(prefix="/api")

# Models
class CharacterThumbnail(BaseModel):
    path: str
    extension: str
    
class CharacterUrl(BaseModel):
    type: str
    url: str

class Character(BaseModel):
    id: int
    name: str
    description: str
    thumbnail: CharacterThumbnail
    resourceURI: str
    urls: List[CharacterUrl]
    comics_available: int = 0
    series_available: int = 0
    stories_available: int = 0
    events_available: int = 0

class FavoriteCharacter(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    character_id: int
    character_name: str
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FavoriteCreate(BaseModel):
    user_id: str
    character_id: int
    character_name: str

class MarvelAPIResponse(BaseModel):
    code: int
    status: str
    data: Dict[str, Any]

# Marvel API Service
class MarvelAPIService:
    def __init__(self):
        self.public_key = MARVEL_PUBLIC_KEY
        self.private_key = MARVEL_PRIVATE_KEY
        self.base_url = MARVEL_BASE_URL
        
    def _generate_auth_params(self):
        """Generate authentication parameters for Marvel API"""
        timestamp = str(int(time.time()))
        hash_string = f"{timestamp}{self.private_key}{self.public_key}"
        hash_md5 = hashlib.md5(hash_string.encode()).hexdigest()
        
        return {
            'ts': timestamp,
            'apikey': self.public_key,
            'hash': hash_md5
        }
    
    @lru_cache(maxsize=100)
    def get_characters(self, name_starts_with: str = None, limit: int = 20, offset: int = 0):
        """Get characters from Marvel API with caching"""
        url = f"{self.base_url}/characters"
        params = self._generate_auth_params()
        params['limit'] = min(limit, 100)  # Marvel API max limit is 100
        params['offset'] = offset
        
        if name_starts_with:
            params['nameStartsWith'] = name_starts_with
            
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['code'] == 200:
                characters = []
                for char_data in data['data']['results']:
                    character = Character(
                        id=char_data['id'],
                        name=char_data['name'],
                        description=char_data.get('description', 'No description available'),
                        thumbnail=CharacterThumbnail(
                            path=char_data['thumbnail']['path'],
                            extension=char_data['thumbnail']['extension']
                        ),
                        resourceURI=char_data['resourceURI'],
                        urls=[CharacterUrl(type=url['type'], url=url['url']) for url in char_data.get('urls', [])],
                        comics_available=char_data.get('comics', {}).get('available', 0),
                        series_available=char_data.get('series', {}).get('available', 0),
                        stories_available=char_data.get('stories', {}).get('available', 0),
                        events_available=char_data.get('events', {}).get('available', 0)
                    )
                    characters.append(character)
                
                return {
                    'characters': characters,
                    'total': data['data']['total'],
                    'count': data['data']['count'],
                    'offset': data['data']['offset']
                }
            else:
                raise HTTPException(status_code=400, detail=f"Marvel API error: {data['status']}")
                
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=503, detail=f"Marvel API unavailable: {str(e)}")
    
    @lru_cache(maxsize=50)
    def get_character_by_id(self, character_id: int):
        """Get specific character by ID"""
        url = f"{self.base_url}/characters/{character_id}"
        params = self._generate_auth_params()
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['code'] == 200 and data['data']['results']:
                char_data = data['data']['results'][0]
                return Character(
                    id=char_data['id'],
                    name=char_data['name'],
                    description=char_data.get('description', 'No description available'),
                    thumbnail=CharacterThumbnail(
                        path=char_data['thumbnail']['path'],
                        extension=char_data['thumbnail']['extension']
                    ),
                    resourceURI=char_data['resourceURI'],
                    urls=[CharacterUrl(type=url['type'], url=url['url']) for url in char_data.get('urls', [])],
                    comics_available=char_data.get('comics', {}).get('available', 0),
                    series_available=char_data.get('series', {}).get('available', 0),
                    stories_available=char_data.get('stories', {}).get('available', 0),
                    events_available=char_data.get('events', {}).get('available', 0)
                )
            else:
                raise HTTPException(status_code=404, detail="Character not found")
                
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=503, detail=f"Marvel API unavailable: {str(e)}")

# Initialize Marvel API service
marvel_service = MarvelAPIService()

# Routes
@api_router.get("/")
async def root():
    return {"message": "Marvel Character Database API"}

@api_router.get("/characters", response_model=Dict[str, Any])
async def get_characters(
    search: Optional[str] = Query(None, description="Search characters by name"),
    limit: int = Query(20, ge=1, le=100, description="Number of characters to return"),
    offset: int = Query(0, ge=0, description="Number of characters to skip")
):
    """Get characters with optional search and pagination"""
    try:
        result = marvel_service.get_characters(
            name_starts_with=search,
            limit=limit,
            offset=offset
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/characters/{character_id}", response_model=Character)
async def get_character(character_id: int):
    """Get specific character by ID"""
    try:
        character = marvel_service.get_character_by_id(character_id)
        return character
    except HTTPException:
        # Re-raise HTTP exceptions (like 404) as-is
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/favorites", response_model=FavoriteCharacter)
async def add_favorite(favorite: FavoriteCreate):
    """Add character to favorites"""
    try:
        # Check if already exists
        existing = await db.favorites.find_one({
            'user_id': favorite.user_id,
            'character_id': favorite.character_id
        })
        
        if existing:
            raise HTTPException(status_code=400, detail="Character already in favorites")
        
        favorite_obj = FavoriteCharacter(**favorite.dict())
        await db.favorites.insert_one(favorite_obj.dict())
        return favorite_obj
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/favorites/{user_id}", response_model=List[FavoriteCharacter])
async def get_favorites(user_id: str):
    """Get user's favorite characters"""
    try:
        favorites = await db.favorites.find({'user_id': user_id}).to_list(1000)
        return [FavoriteCharacter(**fav) for fav in favorites]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/favorites/{user_id}/{character_id}")
async def remove_favorite(user_id: str, character_id: int):
    """Remove character from favorites"""
    try:
        result = await db.favorites.delete_one({
            'user_id': user_id,
            'character_id': character_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Favorite not found")
        
        return {"message": "Favorite removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Include router
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

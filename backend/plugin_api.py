import requests
import aiohttp
import asyncio
from typing import List, Dict, Optional
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class PluginAPI:
    
    def __init__(self):
        self.cache_timeout = 3600
    
    async def search(self, query: str, category: Optional[str] = None, limit: int = 20) -> List[Dict]:
        raise NotImplementedError
    
    async def get_plugin_details(self, plugin_id: str) -> Dict:
        raise NotImplementedError
    
    async def get_download_url(self, plugin_id: str, version: Optional[str] = None) -> str:
        raise NotImplementedError


class ModrinthAPI(PluginAPI):
    
    BASE_URL = "https://api.modrinth.com/v2"
    
    async def search(self, query: str, category: Optional[str] = None, limit: int = 20) -> List[Dict]:
        cache_key = f"modrinth_search_{query}_{category}_{limit}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "query": query,
                    "limit": limit,
                    "facets": '[["project_type:mod"],["categories:bukkit"]]'
                }
                
                if category:
                    params["facets"] = f'[["project_type:mod"],["categories:{category}"]]'
                
                async with session.get(f"{self.BASE_URL}/search", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = []
                        
                        for hit in data.get("hits", []):
                            results.append({
                                "id": hit["project_id"],
                                "slug": hit["slug"],
                                "name": hit["title"],
                                "description": hit["description"],
                                "author": hit["author"],
                                "downloads": hit["downloads"],
                                "icon_url": hit.get("icon_url"),
                                "categories": hit.get("categories", []),
                                "versions": hit.get("versions", []),
                                "date_created": hit.get("date_created"),
                                "date_modified": hit.get("date_modified"),
                                "source": "modrinth"
                            })
                        
                        cache.set(cache_key, results, self.cache_timeout)
                        return results
        except Exception as e:
            logger.error(f"Modrinth API error: {e}")
            return []
        
        return []
    
    async def get_plugin_details(self, plugin_id: str) -> Dict:
        cache_key = f"modrinth_plugin_{plugin_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}/project/{plugin_id}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        async with session.get(f"{self.BASE_URL}/project/{plugin_id}/version") as version_resp:
                            versions = await version_resp.json() if version_resp.status == 200 else []
                        
                        result = {
                            "id": data["id"],
                            "slug": data["slug"],
                            "name": data["title"],
                            "description": data["description"],
                            "body": data.get("body", ""),
                            "author": data.get("team"),
                            "downloads": data["downloads"],
                            "followers": data["followers"],
                            "icon_url": data.get("icon_url"),
                            "categories": data.get("categories", []),
                            "versions": versions,
                            "license": data.get("license", {}).get("name"),
                            "source_url": data.get("source_url"),
                            "issues_url": data.get("issues_url"),
                            "wiki_url": data.get("wiki_url"),
                            "discord_url": data.get("discord_url"),
                            "date_created": data.get("published"),
                            "date_modified": data.get("updated"),
                            "source": "modrinth"
                        }
                        
                        cache.set(cache_key, result, self.cache_timeout)
                        return result
        except Exception as e:
            logger.error(f"Modrinth API error: {e}")
            return {}
        
        return {}
    
    async def get_download_url(self, plugin_id: str, version: Optional[str] = None) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}/project/{plugin_id}/version") as resp:
                    if resp.status == 200:
                        versions = await resp.json()
                        
                        if versions:
                            target_version = versions[0] if not version else next(
                                (v for v in versions if v["version_number"] == version), 
                                versions[0]
                            )
                            
                            files = target_version.get("files", [])
                            if files:
                                return files[0].get("url", "")
        except Exception as e:
            logger.error(f"Modrinth download URL error: {e}")
        
        return ""


class BukkitAPI(PluginAPI):
    
    BASE_URL = "https://dev.bukkit.org/api"
    
    async def search(self, query: str, category: Optional[str] = None, limit: int = 20) -> List[Dict]:
        cache_key = f"bukkit_search_{query}_{category}_{limit}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        results = []
        cache.set(cache_key, results, self.cache_timeout)
        return results
    
    async def get_plugin_details(self, plugin_id: str) -> Dict:
        cache_key = f"bukkit_plugin_{plugin_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        result = {}
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    async def get_download_url(self, plugin_id: str, version: Optional[str] = None) -> str:
        return ""


class SpigotAPI(PluginAPI):
    
    BASE_URL = "https://api.spiget.org/v2"
    
    async def search(self, query: str, category: Optional[str] = None, limit: int = 20) -> List[Dict]:
        cache_key = f"spigot_search_{query}_{category}_{limit}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.BASE_URL}/search/resources/{query}",
                    params={"size": limit}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = []
                        
                        for item in data:
                            results.append({
                                "id": str(item["id"]),
                                "name": item["name"],
                                "tag": item.get("tag", ""),
                                "description": item.get("tag", ""),
                                "author": item.get("author", {}).get("name", "Unknown"),
                                "downloads": item.get("downloads", 0),
                                "rating": item.get("rating", {}).get("average", 0),
                                "icon_url": item.get("icon", {}).get("url", ""),
                                "categories": [item.get("category", {}).get("name", "")],
                                "versions": [item.get("version", {}).get("name", "")],
                                "date_created": item.get("releaseDate"),
                                "date_modified": item.get("updateDate"),
                                "source": "spigot"
                            })
                        
                        cache.set(cache_key, results, self.cache_timeout)
                        return results
        except Exception as e:
            logger.error(f"Spigot API error: {e}")
            return []
        
        return []
    
    async def get_plugin_details(self, plugin_id: str) -> Dict:
        cache_key = f"spigot_plugin_{plugin_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}/resources/{plugin_id}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        async with session.get(f"{self.BASE_URL}/resources/{plugin_id}/versions") as version_resp:
                            versions = await version_resp.json() if version_resp.status == 200 else []
                        
                        async with session.get(f"{self.BASE_URL}/resources/{plugin_id}/reviews") as review_resp:
                            reviews = await review_resp.json() if review_resp.status == 200 else []
                        
                        result = {
                            "id": str(data["id"]),
                            "name": data["name"],
                            "tag": data.get("tag", ""),
                            "description": data.get("tag", ""),
                            "author": data.get("author", {}).get("name", "Unknown"),
                            "downloads": data.get("downloads", 0),
                            "rating": data.get("rating", {}).get("average", 0),
                            "icon_url": data.get("icon", {}).get("url", ""),
                            "premium": data.get("premium", False),
                            "price": data.get("price", 0),
                            "currency": data.get("currency", "USD"),
                            "versions": versions,
                            "reviews": reviews,
                            "likes": data.get("likes", 0),
                            "tested_versions": data.get("testedVersions", []),
                            "links": data.get("links", {}),
                            "date_created": data.get("releaseDate"),
                            "date_modified": data.get("updateDate"),
                            "source": "spigot"
                        }
                        
                        cache.set(cache_key, result, self.cache_timeout)
                        return result
        except Exception as e:
            logger.error(f"Spigot API error: {e}")
            return {}
        
        return {}
    
    async def get_download_url(self, plugin_id: str, version: Optional[str] = None) -> str:
        return f"https://www.spigotmc.org/resources/{plugin_id}/"


class HangarAPI(PluginAPI):
    
    BASE_URL = "https://hangar.papermc.io/api/v1"
    
    async def search(self, query: str, category: Optional[str] = None, limit: int = 20) -> List[Dict]:
        cache_key = f"hangar_search_{query}_{category}_{limit}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "q": query,
                    "limit": limit,
                    "offset": 0
                }
                
                if category:
                    params["category"] = category
                
                async with session.get(f"{self.BASE_URL}/projects", params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = []
                        
                        for project in data.get("result", []):
                            results.append({
                                "id": project["name"],
                                "slug": project["name"],
                                "name": project["name"],
                                "description": project.get("description", ""),
                                "author": project.get("owner", "Unknown"),
                                "downloads": project.get("stats", {}).get("downloads", 0),
                                "stars": project.get("stats", {}).get("stars", 0),
                                "watchers": project.get("stats", {}).get("watchers", 0),
                                "icon_url": project.get("avatarUrl"),
                                "categories": project.get("category", []),
                                "versions": [],
                                "date_created": project.get("createdAt"),
                                "date_modified": project.get("lastUpdated"),
                                "source": "hangar"
                            })
                        
                        cache.set(cache_key, results, self.cache_timeout)
                        return results
        except Exception as e:
            logger.error(f"Hangar API error: {e}")
            return []
        
        return []
    
    async def get_plugin_details(self, plugin_id: str) -> Dict:
        cache_key = f"hangar_plugin_{plugin_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        try:
            async with aiohttp.ClientSession() as session:
                parts = plugin_id.split("/")
                if len(parts) == 2:
                    owner, name = parts
                else:
                    name = plugin_id
                    owner = ""
                
                url = f"{self.BASE_URL}/projects/{name}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        result = {
                            "id": data["name"],
                            "slug": data["name"],
                            "name": data["name"],
                            "description": data.get("description", ""),
                            "author": data.get("owner", "Unknown"),
                            "downloads": data.get("stats", {}).get("downloads", 0),
                            "stars": data.get("stats", {}).get("stars", 0),
                            "watchers": data.get("stats", {}).get("watchers", 0),
                            "icon_url": data.get("avatarUrl"),
                            "categories": data.get("category", []),
                            "license": data.get("settings", {}).get("license", {}).get("name"),
                            "source_url": data.get("settings", {}).get("homepage"),
                            "issues_url": data.get("settings", {}).get("issues"),
                            "date_created": data.get("createdAt"),
                            "date_modified": data.get("lastUpdated"),
                            "source": "hangar"
                        }
                        
                        cache.set(cache_key, result, self.cache_timeout)
                        return result
        except Exception as e:
            logger.error(f"Hangar API error: {e}")
            return {}
        
        return {}
    
    async def get_download_url(self, plugin_id: str, version: Optional[str] = None) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                parts = plugin_id.split("/")
                if len(parts) == 2:
                    owner, name = parts
                else:
                    name = plugin_id
                
                url = f"{self.BASE_URL}/projects/{name}/versions"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if data.get("result"):
                            versions = data["result"]
                            target_version = versions[0] if not version else next(
                                (v for v in versions if v["name"] == version),
                                versions[0]
                            )
                            
                            download_url = f"{self.BASE_URL}/projects/{name}/versions/{target_version['name']}/download"
                            return download_url
        except Exception as e:
            logger.error(f"Hangar download URL error: {e}")
        
        return ""


class PluginManager:
    
    def __init__(self):
        self.apis = {
            'modrinth': ModrinthAPI(),
            'bukkit': BukkitAPI(),
            'spigot': SpigotAPI(),
            'hangar': HangarAPI()
        }
    
    async def search(self, source: str, query: str, category: Optional[str] = None, limit: int = 20) -> List[Dict]:
        api = self.apis.get(source)
        if not api:
            return []
        
        return await api.search(query, category, limit)
    
    async def get_plugin_details(self, source: str, plugin_id: str) -> Dict:
        api = self.apis.get(source)
        if not api:
            return {}
        
        return await api.get_plugin_details(plugin_id)
    
    async def get_download_url(self, source: str, plugin_id: str, version: Optional[str] = None) -> str:
        api = self.apis.get(source)
        if not api:
            return ""
        
        return await api.get_download_url(plugin_id, version)
    
    async def download_plugin(self, source: str, plugin_id: str, version: Optional[str] = None) -> Optional[bytes]:
        download_url = await self.get_download_url(source, plugin_id, version)
        
        if not download_url:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except Exception as e:
            logger.error(f"Plugin download error: {e}")
        
        return None

plugin_manager = PluginManager()

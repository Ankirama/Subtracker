"""
Provider logo and metadata endpoints
"""

import os
import hashlib
import httpx
from pathlib import Path
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse

router = APIRouter(prefix="/providers", tags=["providers"])

# Directory to store cached logos
LOGOS_DIR = Path("/app/logos")
LOGOS_DIR.mkdir(exist_ok=True)

# Common provider domain mappings (same as frontend)
PROVIDER_DOMAINS = {
    # Streaming
    "netflix": "netflix.com",
    "spotify": "spotify.com",
    "youtube": "youtube.com",
    "disney": "disneyplus.com",
    "hbo": "hbo.com",
    "prime video": "primevideo.com",
    "amazon prime": "amazon.com",
    "apple tv": "apple.com",
    "hulu": "hulu.com",
    "paramount": "paramountplus.com",
    # Software & Tools
    "adobe": "adobe.com",
    "microsoft": "microsoft.com",
    "apple": "apple.com",
    "google": "google.com",
    "dropbox": "dropbox.com",
    "github": "github.com",
    "notion": "notion.so",
    "figma": "figma.com",
    "canva": "canva.com",
    "slack": "slack.com",
    "zoom": "zoom.us",
    "asana": "asana.com",
    "trello": "trello.com",
    "monday": "monday.com",
    # Cloud & Hosting
    "aws": "aws.amazon.com",
    "azure": "azure.microsoft.com",
    "google cloud": "cloud.google.com",
    "vercel": "vercel.com",
    "netlify": "netlify.com",
    "heroku": "heroku.com",
    "digitalocean": "digitalocean.com",
    # Social Media
    "linkedin": "linkedin.com",
    "twitter": "twitter.com",
    "facebook": "facebook.com",
    "instagram": "instagram.com",
    "tiktok": "tiktok.com",
    # Productivity
    "office 365": "microsoft.com",
    "google workspace": "google.com",
    "evernote": "evernote.com",
    "lastpass": "lastpass.com",
    "1password": "1password.com",
    "dashlane": "dashlane.com",
    # Email & Marketing
    "mailchimp": "mailchimp.com",
    "sendgrid": "sendgrid.com",
    "constant contact": "constantcontact.com",
    "hubspot": "hubspot.com",
    # E-commerce
    "shopify": "shopify.com",
    "woocommerce": "woocommerce.com",
    "square": "squareup.com",
    # Payment
    "stripe": "stripe.com",
    "paypal": "paypal.com",
    # Communication
    "whatsapp": "whatsapp.com",
    "telegram": "telegram.org",
    "discord": "discord.com",
}


def get_provider_domain(provider_name: str) -> str:
    """Get domain for a provider name"""
    normalized_name = provider_name.lower().strip()

    # Try exact match first
    if normalized_name in PROVIDER_DOMAINS:
        return PROVIDER_DOMAINS[normalized_name]

    # Try partial match
    for key in PROVIDER_DOMAINS:
        if key in normalized_name or normalized_name in key:
            return PROVIDER_DOMAINS[key]

    # Guess domain
    return f"{normalized_name.replace(' ', '')}.com"


def get_logo_cache_path(domain: str) -> Path:
    """Get cached logo file path for a domain"""
    # Use domain hash as filename to avoid filesystem issues
    domain_hash = hashlib.md5(domain.encode()).hexdigest()
    return LOGOS_DIR / f"{domain_hash}.png"


async def download_logo(domain: str) -> bytes | None:
    """Download logo from Clearbit API"""
    url = f"https://logo.clearbit.com/{domain}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0, follow_redirects=True)

            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "image" in content_type:
                    return response.content

            return None
    except Exception as e:
        print(f"Error downloading logo for {domain}: {e}")
        return None


@router.get("/{provider_name}/logo")
async def get_provider_logo(provider_name: str):
    """
    Get provider logo, downloading and caching if necessary.
    Returns 404 if logo cannot be found.
    """
    # Get domain for provider
    domain = get_provider_domain(provider_name)
    cache_path = get_logo_cache_path(domain)

    # Check if logo is cached
    if cache_path.exists():
        return FileResponse(
            cache_path,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
            },
        )

    # Download logo
    logo_data = await download_logo(domain)

    if logo_data is None:
        raise HTTPException(status_code=404, detail="Logo not found")

    # Cache logo
    cache_path.write_bytes(logo_data)

    return Response(
        content=logo_data,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400",
        },
    )

"""
Photo Picker endpoints for selecting and managing Google Photos.
"""

import json

import requests
from fastapi import APIRouter, HTTPException, Request
from google.auth.transport.requests import Request as GoogleRequest
from pydantic import BaseModel

from ..auth.google_photos_auth import GooglePhotosAPI

picker_router = APIRouter(prefix="/api", tags=["picker"])


class PickerSessionRequest(BaseModel):
    """Request model for creating a picker session."""

    picker_session_id: str


class PhotoMetadataRequest(BaseModel):
    """Request model for fetching photo metadata."""

    media_items: list[str]


@picker_router.post("/create-session")
async def create_picker_session(request: Request):
    """
    Create a Google Photos Picker session.
    This endpoint initiates the picker flow and returns the picker URI.
    """
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in picker_router.sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = picker_router.sessions[session_id]
    if not session_data.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        # Get credentials from session
        creds = GooglePhotosAPI.credentials_from_json(session_data.credentials)

        # Create picker session using Google Photos Picker API
        picker_api_url = "https://photospicker.googleapis.com/v1/sessions"

        headers = {
            "Authorization": f"Bearer {creds.token}",
        }

        # Request body for creating a picker session
        # POST request with no body - the API creates a session with default config
        response = requests.post(picker_api_url, headers=headers)

        if response.status_code == 401:
            # Token might be expired, try to refresh
            creds.refresh(GoogleRequest())
            session_data.credentials = creds.to_json()

            # Retry with refreshed token
            headers["Authorization"] = f"Bearer {creds.token}"
            response = requests.post(picker_api_url, headers=headers, json=body)

        if not response.ok:
            error_detail = response.json() if response.content else {"error": "Unknown error"}
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to create picker session: {error_detail}",
            )

        result = response.json()

        # Store the session ID for later polling
        session_data.picker_session_id = result.get("id")

        return {
            "sessionId": result.get("id"),
            "pickerUri": result.get("pickerUri"),
            "pollInterval": result.get("pollingConfig", {}).get("pollInterval", "5s").rstrip("s"),
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"API request failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@picker_router.get("/session-status")
async def get_session_status(request: Request):
    """
    Check the status of the picker session.
    Used for polling to see if user has selected photos.
    """
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in picker_router.sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = picker_router.sessions[session_id]

    if not session_data.picker_session_id:
        return {"mediaItemsSet": False, "status": "no_session"}

    try:
        # Get credentials from session
        creds = GooglePhotosAPI.credentials_from_json(session_data.credentials)

        # Poll the picker session status
        picker_session_url = (
            f"https://photospicker.googleapis.com/v1/sessions/{session_data.picker_session_id}"
        )

        headers = {
            "Authorization": f"Bearer {creds.token}",
        }

        response = requests.get(picker_session_url, headers=headers)

        if response.status_code == 401:
            # Token might be expired, try to refresh
            creds.refresh(GoogleRequest())
            session_data.credentials = creds.to_json()

            # Retry with refreshed token
            headers["Authorization"] = f"Bearer {creds.token}"
            response = requests.get(picker_session_url, headers=headers)

        if not response.ok:
            return {"mediaItemsSet": False, "status": "error"}

        result = response.json()

        # Check if media items have been set
        media_items_set = bool(result.get("mediaItemsSet"))

        return {
            "mediaItemsSet": media_items_set,
            "status": "ready" if media_items_set else "pending",
        }

    except Exception as e:
        return {"mediaItemsSet": False, "status": "error", "error": str(e)}


@picker_router.get("/list-selected")
async def list_selected_photos(request: Request):
    """
    List photos that were selected via the picker.
    Returns photo metadata including URLs and EXIF data.
    """
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in picker_router.sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = picker_router.sessions[session_id]
    if not session_data.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not session_data.picker_session_id:
        return {"items": [], "count": 0}

    try:
        # Get credentials from session
        creds = GooglePhotosAPI.credentials_from_json(session_data.credentials)

        # Get the picker session to retrieve media item IDs
        picker_session_url = (
            f"https://photospicker.googleapis.com/v1/sessions/{session_data.picker_session_id}"
        )

        headers = {
            "Authorization": f"Bearer {creds.token}",
        }

        response = requests.get(picker_session_url, headers=headers)

        if response.status_code == 401:
            # Token might be expired, try to refresh
            creds.refresh(GoogleRequest())
            session_data.credentials = creds.to_json()

            # Retry with refreshed token
            headers["Authorization"] = f"Bearer {creds.token}"
            response = requests.get(picker_session_url, headers=headers)

        if not response.ok:
            error_msg = f"Failed to get picker session: {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {response.text}"
            print(f"ERROR: {error_msg}")
            raise HTTPException(status_code=response.status_code, detail=error_msg)

        result = response.json()
        print(f"Full picker session response: {json.dumps(result, indent=2)}")
        print(f"Available keys in response: {list(result.keys())}")

        # Check if mediaItemsSet is True (it's a boolean flag)
        media_items_set = result.get("mediaItemsSet", False)
        if not media_items_set:
            print("No photos selected yet (mediaItemsSet is False)")
            return {"items": [], "count": 0}

        # Try different possible fields where media items might be
        media_items = None

        # Check for various possible field names
        for field in ["mediaItems", "items", "selectedMediaItems", "photos"]:
            if field in result:
                media_items = result[field]
                print(f"Found media items in field '{field}'")
                break

        # If media items are not in the session, they might need to be fetched separately
        # The Picker API might store media item IDs that we need to fetch from Photos Library API
        if media_items is None:
            print("Media items not found in session response")
            print("Checking for media item IDs or references...")

            # Look for mediaItemIds or similar fields
            for field in ["mediaItemIds", "itemIds", "selectedIds"]:
                if field in result:
                    item_ids = result[field]
                    print(f"Found {len(item_ids)} media item IDs in field '{field}': {item_ids}")

                    # Fetch full media item details from Photos Library API
                    items = []
                    photos_api_url = "https://photoslibrary.googleapis.com/v1/mediaItems:batchGet"

                    for i in range(0, len(item_ids), 50):
                        batch_ids = item_ids[i : i + 50]
                        params = [("mediaItemIds", item_id) for item_id in batch_ids]

                        batch_response = requests.get(
                            photos_api_url, headers=headers, params=params
                        )

                        if batch_response.ok:
                            batch_result = batch_response.json()
                            for item_result in batch_result.get("mediaItemResults", []):
                                media_item = item_result.get("mediaItem")
                                if media_item:
                                    items.append(media_item)

                    return {"items": items, "count": len(items)}

            # Use the CORRECT Picker API endpoint as per documentation
            print("Using correct Picker API mediaItems.list endpoint...")

            # The correct endpoint: GET /v1/mediaItems?sessionId={sessionId}
            media_items_url = "https://photospicker.googleapis.com/v1/mediaItems"
            params = {
                "sessionId": session_data.picker_session_id,
                "pageSize": 100,
                # Try requesting specific fields including location
                "view": "FULL",  # Request full metadata
            }

            print(
                f"Fetching from: {media_items_url} with sessionId={session_data.picker_session_id}"
            )
            media_response = requests.get(media_items_url, headers=headers, params=params)

            if media_response.ok:
                result = media_response.json()
                print(f"SUCCESS! Media items response: {json.dumps(result, indent=2)}")
                raw_items = result.get("mediaItems", [])

                # Transform the response to match frontend expectations
                items = []
                for item in raw_items:
                    media_file = item.get("mediaFile", {})
                    metadata = media_file.get("mediaFileMetadata", {})
                    photo_metadata = metadata.get("photoMetadata", {})

                    # Extract location if available
                    location = None
                    if "location" in item:
                        location = item.get("location")
                    elif "location" in metadata:
                        location = metadata.get("location")

                    transformed_item = {
                        "id": item.get("id"),
                        "baseUrl": media_file.get("baseUrl"),
                        "mimeType": media_file.get("mimeType"),
                        "filename": media_file.get("filename"),
                        "mediaMetadata": {
                            "creationTime": item.get("createTime"),
                            "width": metadata.get("width"),
                            "height": metadata.get("height"),
                            "photo": photo_metadata,
                            "cameraMake": metadata.get("cameraMake"),
                            "cameraModel": metadata.get("cameraModel"),
                        },
                    }

                    # Add location if it exists
                    if location:
                        transformed_item["mediaMetadata"]["location"] = location
                        # Also add it at the root level for easier access
                        transformed_item["location"] = location

                    items.append(transformed_item)

                # Log the first item to see full structure including location
                if items:
                    print(f"Sample transformed item: {json.dumps(items[0], indent=2)}")

                print(f"Found {len(items)} media items! Transformed for frontend.")
                return {"items": items, "count": len(items)}
            else:
                print(f"Media items request failed: {media_response.status_code}")
                try:
                    error_detail = media_response.json()
                    print(f"Error detail: {json.dumps(error_detail, indent=2)}")
                except:
                    print(f"Error text: {media_response.text[:500]}")

            print("Trying other endpoints as fallback...")

            # Method 1: Try listMediaItems on the session with POST and proper body
            list_url = f"https://photospicker.googleapis.com/v1/sessions/{session_data.picker_session_id}:listMediaItems"
            print(f"Trying POST with body: {list_url}")

            headers_with_content = headers.copy()
            headers_with_content["Content-Type"] = "application/json"

            # Try with pageSize parameter
            list_body = {"pageSize": 100}
            list_response = requests.post(list_url, headers=headers_with_content, json=list_body)

            if list_response.ok:
                list_result = list_response.json()
                print(f"listMediaItems POST response: {json.dumps(list_result, indent=2)}")
                items = list_result.get("mediaItems", [])
                if items:
                    return {"items": items, "count": len(items)}
            else:
                print(f"listMediaItems POST failed: {list_response.status_code}")
                try:
                    error_detail = list_response.json()
                    print(f"Error detail: {json.dumps(error_detail, indent=2)}")
                except:
                    print(f"Error text: {list_response.text[:200]}")

            # Also try GET
            print(f"Trying GET: {list_url}")
            list_response_get = requests.get(list_url, headers=headers)
            if list_response_get.ok:
                list_result = list_response_get.json()
                print(f"listMediaItems GET response: {json.dumps(list_result, indent=2)}")
                items = list_result.get("mediaItems", [])
                if items:
                    return {"items": items, "count": len(items)}
            else:
                print(f"listMediaItems GET failed: {list_response_get.status_code}")

            # Method 2: Try POST to list
            print(f"Trying POST to: {list_url}")
            list_response2 = requests.post(list_url, headers=headers, json={})
            if list_response2.ok:
                list_result2 = list_response2.json()
                print(f"POST listMediaItems response: {json.dumps(list_result2, indent=2)}")
                items = list_result2.get("mediaItems", [])
                if items:
                    return {"items": items, "count": len(items)}
            else:
                print(f"POST listMediaItems failed: {list_response2.status_code}")

            # Method 3: Try sessions.mediaItems.list
            media_items_list_url = f"https://photospicker.googleapis.com/v1/sessions/{session_data.picker_session_id}/mediaItems"
            print(f"Trying: {media_items_list_url}")
            media_response = requests.get(media_items_list_url, headers=headers)
            if media_response.ok:
                media_result = media_response.json()
                print(f"mediaItems list response: {json.dumps(media_result, indent=2)}")
                items = media_result.get("mediaItems", [])
                if items:
                    return {"items": items, "count": len(items)}
            else:
                print(f"mediaItems list failed: {media_response.status_code}")

            # Last resort - return empty with full debug info
            print("All Picker API methods failed - returning empty with debug info")
            print("The Picker API might work differently than expected")
            print("You may need to handle the picker selection via JavaScript callback")
            return {
                "items": [],
                "count": 0,
                "debug": {
                    "session": result,
                    "message": "Photos selected but unable to retrieve via backend API. The Google Photos Picker may require client-side handling.",
                },
            }

        # If we found media items directly in the response
        print(f"Successfully fetched {len(media_items)} items from session")
        return {"items": media_items, "count": len(media_items)}

    except requests.RequestException as e:
        print(f"Request exception: {str(e)}")
        raise HTTPException(status_code=500, detail=f"API request failed: {str(e)}")
    except Exception as e:
        print(f"Unexpected exception: {str(e)}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch photos: {str(e)}")


@picker_router.post("/picker/session")
async def store_picker_session(request: Request, session_request: PickerSessionRequest):
    """Store the picker session ID from the frontend."""
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in picker_router.sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = picker_router.sessions[session_id]
    session_data.picker_session_id = session_request.picker_session_id

    return {"status": "success", "picker_session_id": session_request.picker_session_id}


@picker_router.post("/picker/metadata")
async def get_photo_metadata(request: Request, metadata_request: PhotoMetadataRequest):
    """
    Fetch metadata for selected photos.
    This endpoint receives media item IDs from the picker.
    """
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in picker_router.sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = picker_router.sessions[session_id]
    if not session_data.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Here you would use the Google Photos API to fetch metadata
    # For now, return a placeholder response
    return {
        "status": "success",
        "media_items": metadata_request.media_items,
        "count": len(metadata_request.media_items),
    }


@picker_router.get("/picker/status")
async def picker_status(request: Request):
    """Check picker session status."""
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in picker_router.sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = picker_router.sessions[session_id]

    return {
        "authenticated": bool(session_data.credentials),
        "picker_session_active": bool(session_data.picker_session_id),
    }

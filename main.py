from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import os
import random
import jwt
import requests
from datetime import datetime
from typing import Optional, Dict, Any

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Anthropic client - keeping your working version
api_key = os.getenv("ANTHROPIC_API_KEY")
clerk_secret = os.getenv("CLERK_SECRET_KEY")
print(f"DEBUG: API key from environment: {'Found' if api_key else 'Not found'}")
print(f"DEBUG: Clerk secret from environment: {'Found' if clerk_secret else 'Not found'}")

if not api_key:
    print("ERROR: ANTHROPIC_API_KEY not found in environment!")
    raise HTTPException(status_code=500, detail="API key not configured")

print(f"DEBUG: API key loaded successfully")
client = anthropic.Anthropic(api_key=api_key)

# In-memory storage for user conversations (in production, use a real database)
user_conversations: Dict[str, list] = {}

# Clerk JWT verification function
async def verify_clerk_token(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """Verify Clerk JWT token and return user info"""
    if not authorization or not clerk_secret:
        return None
    
    try:
        # Extract token from "Bearer <token>"
        token = authorization.replace("Bearer ", "")
        
        # Simple verification for demo (in production, use proper JWT verification)
        decoded = jwt.decode(
            token,
            options={"verify_signature": False},  # Simplified for demo
            algorithms=["RS256"]
        )
        
        return decoded
    except Exception as e:
        print(f"DEBUG: Token verification error: {e}")
        return None

class RelationshipSituation(BaseModel):
    situation: str
    user_id: Optional[str] = None

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/philosophy-mix")
async def get_philosophy_mix():
    philosophy_weights = {
        'christian': 0.30,
        'buddhist': 0.30,
        'taoist': 0.10,
        'secular_humanist': 0.10,
        'stoic': 0.20
    }
    
    philosophy_display = {}
    display_names = {
        'christian': 'Christian',
        'buddhist': 'Buddhist',
        'taoist': 'Taoist',
        'secular_humanist': 'Secular Humanist',
        'stoic': 'Stoic'
    }
    
    for philosophy, weight in philosophy_weights.items():
        philosophy_display[philosophy] = {
            'name': display_names[philosophy],
            'percentage': round(weight * 100, 1),
            'weight': weight
        }
    
    return {
        'philosophy_mix': philosophy_display,
        'total_traditions': len(philosophy_weights),
        'description': 'Babushka draws wisdom from diverse global traditions.'
    }

@app.post("/advice")
async def get_relationship_advice(
    situation: RelationshipSituation,
    user_info: Optional[Dict[str, Any]] = Depends(verify_clerk_token)
):
    try: 
        print(f"DEBUG: Received situation: {situation.situation}")
        
        # Get user ID from auth token if available
        user_id = None
        if user_info:
            user_id = user_info.get("sub")  # Clerk uses 'sub' for user ID
            print(f"DEBUG: Authenticated user: {user_id}")
        
        # Store user message if authenticated
        if user_id:
            if user_id not in user_conversations:
                user_conversations[user_id] = []
            
            user_conversations[user_id].append({
                "timestamp": datetime.now().isoformat(),
                "type": "user_message", 
                "content": situation.situation
            })
        
        philosophy_weights = {
            'christian': 0.30,
            'buddhist': 0.30,
            'taoist': 0.10,
            'secular_humanist': 0.10,
            'stoic': 0.20
        }
        
        available_philosophies = [k for k, v in philosophy_weights.items() if v > 0]
        available_weights = [philosophy_weights[k] for k in available_philosophies]
        
        selected_philosophies = random.choices(
            available_philosophies,
            weights=available_weights,
            k=min(3, len(available_philosophies))
        )
        
        print(f"DEBUG: Selected philosophies: {selected_philosophies}")
        
        philosophy_prompts = {
            'christian': "Focus on love, forgiveness, patience, and treating others with dignity and respect.",
            'buddhist': "Emphasize compassion, wisdom, truth, emancipation from earthly desires and delusion.",
            'taoist': "Emphasize natural flow, balance, not forcing situations, and finding harmony.",
            'secular_humanist': "Focus on reason, empathy, human dignity, and evidence-based problem solving.",
            'stoic': "Emphasize acceptance of what you cannot control and focusing on your own actions and responses."
        }
        
        philosophy_guidance = "\n".join([
            f"- {philosophy_prompts[phil]}" for phil in selected_philosophies
        ])
        
        prompt = f"""You are Babushka, a wise relationship advisor who draws from the collective wisdom of many cultures and generations. You speak with the warm, caring voice of a grandmother who has seen many relationships succeed and fail.

Your advice should incorporate these philosophical perspectives:
{philosophy_guidance}

Situation: {situation.situation}

Provide warm, practical relationship advice that:
1. Shows empathy and understanding
2. Offers concrete, actionable steps
3. Draws from traditional wisdom while being relevant to modern relationships
4. Is encouraging but realistic
5. Uses gentle, grandmother-like language

Keep your response between 100-200 words. Address the person as "dearest child" or similar endearing terms."""

        print("DEBUG: About to call Anthropic API")
        
        # Keep your exact working API call format
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=300,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        advice_text = response.content[0].text
        print(f"DEBUG: Anthropic response received successfully")
        
        # Store bot response if authenticated
        if user_id:
            user_conversations[user_id].append({
                "timestamp": datetime.now().isoformat(),
                "type": "bot_response",
                "content": advice_text
            })
        
        return {"advice": advice_text, "user_id": user_id}
        
    except Exception as e:
        print(f"DEBUG: Exception caught: {str(e)}")
        print(f"DEBUG: Exception type: {type(e)}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error generating advice: {str(e)}")

@app.get("/conversations/{user_id}")
async def get_user_conversations(
    user_id: str,
    user_info: Optional[Dict[str, Any]] = Depends(verify_clerk_token)
):
    """Get conversation history for authenticated user"""
    if not user_info:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Verify user can only access their own conversations
    token_user_id = user_info.get("sub")
    if token_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    conversations = user_conversations.get(user_id, [])
    return {"user_id": user_id, "conversations": conversations}

@app.get("/stats")
async def get_stats(user_info: Optional[Dict[str, Any]] = Depends(verify_clerk_token)):
    """Get usage statistics"""
    total_users = len(user_conversations)
    total_conversations = sum(len(convs) for convs in user_conversations.values())
    
    stats = {
        "total_users": total_users,
        "total_conversations": total_conversations,
        "authenticated": user_info is not None
    }
    
    if user_info:
        user_id = user_info.get("sub")
        user_conversation_count = len(user_conversations.get(user_id, []))
        stats["user_conversation_count"] = user_conversation_count
    
    return stats

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import jwt
from passlib.context import CryptContext
import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, messaging

from database import get_db
from models import User, Meal, DietPlan, Challenge, ChallengeParticipant, Progress, DietPlanResponse


# Load environment variables
load_dotenv()

# Initialize Firebase Admin SDK
#cred = credentials.Certificate(os.getenv("FIREBASE_CREDENTIALS_PATH"))
#firebase_admin.initialize_app(cred)

app = FastAPI(
    title="Weight Loss App Backend",
    description="Backend API for the weight loss app with personalized diet plans and challenges",
    version="1.0.0"
)

# Configure CORS for mobile app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"

# Pydantic models
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    biotype: str
    current_weight: float
    target_weight: float
    height: float
    age: int
    gender: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    biotype: str
    current_weight: float
    target_weight: float
    height: float
    age: int
    gender: str
    device_token: Optional[str] = None
    device_type: Optional[str] = None

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class MealCreate(BaseModel):
    name: str
    description: str
    calories: int
    protein: float
    carbs: float
    fat: float
    meal_type: str
    image_url: Optional[str] = None

class DietPlanCreate(BaseModel):
    meals: List[MealCreate]
    total_calories: int

class ChallengeCreate(BaseModel):
    name: str
    description: str
    start_date: datetime
    end_date: datetime
    target_weight_loss: float
    image_url: Optional[str] = None

class ProgressCreate(BaseModel):
    weight: float
    notes: Optional[str] = None
    image_url: Optional[str] = None

class Notification(BaseModel):
    title: str
    body: str
    data: Optional[Dict] = None

# Helper functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except jwt.JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

async def send_push_notification(user_id: int, notification: Notification, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.device_token:
        return
    
    message = messaging.Message(
        notification=messaging.Notification(
            title=notification.title,
            body=notification.body,
        ),
        data=notification.data or {},
        token=user.device_token,
    )
    
    try:
        messaging.send(message)
    except Exception as e:
        print(f"Error sending push notification: {e}")

# Authentication endpoints
@app.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# User endpoints
@app.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    db_user = User(
        **user.dict(exclude={"password"}),
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.put("/users/device-token")
async def update_device_token(
    device_token: str,
    device_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    current_user.device_token = device_token
    current_user.device_type = device_type
    db.commit()
    return {"message": "Device token updated successfully"}

# Diet plan endpoints
@app.post("/diet-plans", response_model=DietPlanResponse)
async def create_diet_plan(
    diet_plan: DietPlanCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_diet_plan = DietPlan(
        user_id=current_user.id,
        total_calories=diet_plan.total_calories
    )
    db.add(db_diet_plan)
    db.commit()
    db.refresh(db_diet_plan)
    
    for meal in diet_plan.meals:
        db_meal = Meal(**meal.dict(), diet_plan_id=db_diet_plan.id)
        db.add(db_meal)
    
    db.commit()
    db.refresh(db_diet_plan)
    return db_diet_plan

@app.get("/diet-plans/me", response_model=DietPlanResponse)
async def get_my_diet_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    diet_plan = db.query(DietPlan).filter(DietPlan.user_id == current_user.id).first()
    if not diet_plan:
        raise HTTPException(status_code=404, detail="Diet plan not found")
    return diet_plan

# Challenge endpoints
@app.post("/challenges", response_model=ChallengeResponse)
async def create_challenge(
    challenge: ChallengeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_challenge = Challenge(
        **challenge.dict(),
        created_by=current_user.id
    )
    db.add(db_challenge)
    db.commit()
    db.refresh(db_challenge)
    return db_challenge

@app.get("/challenges", response_model=List[ChallengeResponse])
async def get_challenges(db: Session = Depends(get_db)):
    return db.query(Challenge).all()

@app.post("/challenges/{challenge_id}/join")
async def join_challenge(
    challenge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    existing_participant = db.query(ChallengeParticipant).filter(
        ChallengeParticipant.challenge_id == challenge_id,
        ChallengeParticipant.user_id == current_user.id
    ).first()
    
    if not existing_participant:
        participant = ChallengeParticipant(
            challenge_id=challenge_id,
            user_id=current_user.id
        )
        db.add(participant)
        db.commit()
    
    return {"message": "Successfully joined challenge"}

# Progress tracking endpoints
@app.post("/progress", response_model=Progress)
async def add_progress(
    progress: ProgressCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_progress = Progress(
        **progress.dict(),
        user_id=current_user.id
    )
    db.add(db_progress)
    db.commit()
    db.refresh(db_progress)
    return db_progress

@app.get("/progress/me", response_model=List[Progress])
async def get_my_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Progress).filter(Progress.user_id == current_user.id).all()

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Hello from Allana's API!"} 
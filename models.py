from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, DateTime, Enum, JSON
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import enum

class Biotype(str, enum.Enum):
    ECTOMORPH = "ectomorph"
    MESOMORPH = "mesomorph"
    ENDOMORPH = "endomorph"

class MealType(str, enum.Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"

class DeviceType(str, enum.Enum):
    IOS = "ios"
    ANDROID = "android"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    biotype = Column(Enum(Biotype))
    current_weight = Column(Float)
    target_weight = Column(Float)
    height = Column(Float)
    age = Column(Integer)
    gender = Column(String)
    device_token = Column(String, nullable=True)
    device_type = Column(Enum(DeviceType), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    diet_plans = relationship("DietPlan", back_populates="user")
    progress_records = relationship("Progress", back_populates="user")
    challenges_created = relationship("Challenge", back_populates="creator")
    challenges_participated = relationship("ChallengeParticipant", back_populates="user")

class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    calories = Column(Integer)
    protein = Column(Float)
    carbs = Column(Float)
    fat = Column(Float)
    meal_type = Column(Enum(MealType))
    image_url = Column(String, nullable=True)
    diet_plan_id = Column(Integer, ForeignKey("diet_plans.id"))

    diet_plan = relationship("DietPlan", back_populates="meals")

class DietPlan(Base):
    __tablename__ = "diet_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    total_calories = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="diet_plans")
    meals = relationship("Meal", back_populates="diet_plan")

class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    target_weight_loss = Column(Float)
    created_by = Column(Integer, ForeignKey("users.id"))
    image_url = Column(String, nullable=True)

    creator = relationship("User", back_populates="challenges_created")
    participants = relationship("ChallengeParticipant", back_populates="challenge")

class ChallengeParticipant(Base):
    __tablename__ = "challenge_participants"

    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    joined_at = Column(DateTime, default=datetime.utcnow)

    challenge = relationship("Challenge", back_populates="participants")
    user = relationship("User", back_populates="challenges_participated")

class Progress(Base):
    __tablename__ = "progress"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    weight = Column(Float)
    date = Column(DateTime, default=datetime.utcnow)
    notes = Column(String, nullable=True)
    image_url = Column(String, nullable=True)

    user = relationship("User", back_populates="progress_records")



# ✅ AGORA começa o modelo Pydantic FORA da classe Progress:

from pydantic import BaseModel
from datetime import datetime

class DietPlanResponse(BaseModel):
    id: int
    user_id: int
    total_calories: int
    created_at: datetime

    class Config:
        orm_mode = True
        
    class ChallengeResponse(BaseModel):
    id: int
    name: str
    description: str
    start_date: datetime
    end_date: datetime
    target_weight_loss: float
    created_by: int
    image_url: Optional[str] = None

    class Config:
        from_attributes = True  # <-- this replaces orm_mode in Pydantic v2
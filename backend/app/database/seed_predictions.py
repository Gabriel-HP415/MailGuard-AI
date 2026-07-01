"""Seed predictions data for testing dashboard."""

from datetime import datetime, timedelta
import random

from app.core.constants import EmailClass, ThreatLevel
from app.database.connection import SessionLocal
from app.models.email import Email
from app.models.prediction import Prediction
from app.models.user import User


SAMPLE_EMAILS = [
    {"sender": "support@legitbank.com", "subject": "Your account statement is ready", "body": "Dear Customer,\n\nYour monthly statement for March 2024 is now available in your online banking portal.\n\nPlease log in to view your account details.\n\nBest regards,\nLegitBank Support"},
    {"sender": "noreply@socialnetwork.com", "subject": "New friend request", "body": "You have a new friend request from John Doe.\n\nClick here to accept or decline."},
    {"sender": "newsletter@retailer.com", "subject": "Weekly deals - 50% off!", "body": "Check out this week's amazing deals at our store!\n\nShop now for the best discounts."},
    {"sender": "hr@company.com", "subject": "Meeting tomorrow at 2pm", "body": "Hi team,\n\nJust a reminder about our team meeting tomorrow at 2pm in conference room B.\n\nRegards,\nHR"},
    {"sender": "alert@bank.com", "subject": "URGENT: Suspicious login attempt detected", "body": "We detected a suspicious login attempt on your account.\n\nIf this wasn't you, click here immediately to secure your account: http://bit.ly/fakesite\n\nAct now!"},
    {"sender": "winner@lottery-intl.com", "subject": "Congratulations! You've won $5,000,000!", "body": "CONGRATULATIONS!!!\n\nYou have been randomly selected as the winner of our International Lottery!\n\nTo claim your $5,000,000 prize, send us your bank details and ID.\n\nAct now!"},
    {"sender": "support@apple.com", "subject": "Your Apple ID was used to sign in to iCloud", "body": "Your Apple ID (john@example.com) was used to sign in to iCloud on a new device.\n\nIf this wasn't you, please secure your account immediately."},
    {"sender": "amazon@orders.amazon.com", "subject": "Your Amazon order has shipped", "body": "Your package is on its way!\n\nTrack your delivery with the link below."},
    {"sender": "free-money@givaway.net", "subject": "FREE MONEY - Limited time offer!", "body": "Get $1000 FREE just for clicking this link!\n\nNo catch! Just fill out this form with your credit card info to verify your identity."},
    {"sender": "boss@company.com", "subject": "Quick favor needed", "body": "Hi,\n\nI'm in a meeting and need you to buy some gift cards for client gifts.\n\nI'll reimburse you later. Can you send me the codes ASAP?"},
]

CLASS_CONFIGS = {
    EmailClass.NORMAL: {"risk": (5, 20), "threat": ThreatLevel.LOW},
    EmailClass.NOTIFICATION: {"risk": (10, 30), "threat": ThreatLevel.LOW},
    EmailClass.SPAM: {"risk": (50, 75), "threat": ThreatLevel.MEDIUM},
    EmailClass.SCAM: {"risk": (80, 100), "threat": ThreatLevel.HIGH},
}


def seed_predictions():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.role == "admin").first()
        if not user:
            print("No admin user found!")
            return
        
        existing = db.query(Prediction).count()
        if existing > 0:
            print(f"Already have {existing} predictions. Skipping seed.")
            return
        
        emails_to_create = []
        predictions_to_create = []
        
        # Create 20 predictions over the last 30 days
        for i in range(20):
            days_ago = random.randint(0, 29)
            hours_ago = random.randint(0, 23)
            created_at = datetime.utcnow() - timedelta(days=days_ago, hours=hours_ago)
            
            sample = random.choice(SAMPLE_EMAILS)
            
            # Determine class based on email type
            if "URGENT" in sample["subject"] or "lottery" in sample["sender"] or "free" in sample["subject"].lower():
                email_class = random.choice([EmailClass.SCAM, EmailClass.SPAM])
            elif "newsletter" in sample["sender"] or "deals" in sample["subject"].lower():
                email_class = random.choice([EmailClass.SPAM, EmailClass.NOTIFICATION])
            else:
                email_class = random.choice([EmailClass.NORMAL, EmailClass.NOTIFICATION])
            
            config = CLASS_CONFIGS[email_class]
            risk_score = random.uniform(*config["risk"])
            
            email = Email(
                user_id=user.id,
                sender=sample["sender"],
                subject=sample["subject"],
                body_text=sample["body"],
                created_at=created_at,
            )
            db.add(email)
            db.flush()
            
            prediction = Prediction(
                email_id=email.id,
                user_id=user.id,
                model_version_id=1,
                predicted_class=email_class,
                class_index=email_class.index,
                confidence=round(random.uniform(0.7, 0.99), 4),
                risk_score=round(risk_score, 2),
                threat_level=config["threat"],
                probabilities=[round(random.uniform(0.1, 0.9), 4) for _ in range(4)],
                inference_time_ms=random.randint(50, 200),
                created_at=created_at,
            )
            db.add(prediction)
            emails_to_create.append(email)
            predictions_to_create.append(prediction)
        
        db.commit()
        print(f"Created {len(emails_to_create)} emails and {len(predictions_to_create)} predictions!")
        
    finally:
        db.close()


if __name__ == "__main__":
    seed_predictions()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import numpy as np
from typing import List, Dict
from model_training import HybridPredictionModel
from feature_engineering import FeatureEngineering

app = FastAPI(title="Football Prediction AI API")

# Load model (assuming it's already trained and saved)
try:
    model = HybridPredictionModel.load_model('ensemble_model.pkl')
except:
    print("Warning: Model not found. Using a dummy model for demonstration.")
    model = HybridPredictionModel()
    # Dummy train
    X_dummy = np.random.rand(10, 7)
    y_dummy = np.random.randint(0, 3, 10)
    model.train(X_dummy, y_dummy)

fe = FeatureEngineering()

class MatchRequest(BaseModel):
    home_team: str
    away_team: str
    home_form_goals_scored: float
    away_form_goals_scored: float
    home_form_goals_conceded: float
    away_form_goals_conceded: float
    h2h_home_win_rate: float
    home_days_rest: int
    away_days_rest: int

class PredictionResponse(BaseModel):
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    confidence: str
    explanation: str

@app.post("/predict", response_model=PredictionResponse)
def predict_match(match: MatchRequest):
    try:
        # 1. Prepare data
        data = pd.DataFrame([match.dict()])
        
        # We drop team names for prediction
        features = data.drop(columns=['home_team', 'away_team'])
        
        # In a real app, you'd scale these features using the saved scaler from training
        # features = fe.scaler.transform(features)
        
        # 2. Predict
        probs = model.predict_proba(features)[0]
        
        # 3. Calculate confidence and explanation
        max_prob = np.max(probs)
        if max_prob > 0.6:
            confidence = "High"
        elif max_prob > 0.45:
            confidence = "Medium"
        else:
            confidence = "Low"
            
        # Simple explanation logic based on input features
        explanation = f"Prediction based on recent form. "
        if match.home_form_goals_scored > match.away_form_goals_scored:
            explanation += f"{match.home_team} shows stronger attacking form. "
        if match.home_days_rest > match.away_days_rest + 2:
            explanation += f"{match.home_team} has a significant rest advantage."
            
        return PredictionResponse(
            home_win_prob=round(probs[2] * 100, 1),
            draw_prob=round(probs[1] * 100, 1),
            away_win_prob=round(probs[0] * 100, 1),
            confidence=confidence,
            explanation=explanation
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

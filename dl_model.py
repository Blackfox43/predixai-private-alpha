import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.base import BaseEstimator, ClassifierMixin

class MatchSequenceDataset(Dataset):
    def __init__(self, X, y=None):
        # X shape expected: (num_samples, seq_length, num_features)
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long) if y is not None else None

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        if self.y is not None:
            return self.X[idx], self.y[idx]
        return self.X[idx]

class FormTrackerGRU(nn.Module):
    """
    GRU-based neural network for tracking team form over a sequence of matches.
    """
    def __init__(self, input_size, hidden_size=64, num_layers=2, num_classes=3, dropout=0.2):
        super(FormTrackerGRU, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # GRU layer for time-series processing
        self.gru = nn.GRU(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout if num_layers > 1 else 0)
        
        # Fully connected layers
        self.fc1 = nn.Linear(hidden_size, 32)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(32, num_classes)
        
    def forward(self, x):
        # x shape: (batch_size, seq_length, input_size)
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        
        # Forward propagate GRU
        out, _ = self.gru(x, h0)
        
        # Decode the hidden state of the last time step
        out = out[:, -1, :]
        
        out = self.fc1(out)
        out = self.relu(out)
        out = self.dropout(out)
        out = self.fc2(out)
        return out

class DeepFormModel(BaseEstimator, ClassifierMixin):
    """
    Scikit-learn compatible wrapper for the PyTorch GRU model.
    Allows seamless integration into the HybridPredictionModel ensemble.
    """
    def __init__(self, input_size=7, hidden_size=64, num_layers=2, epochs=15, batch_size=32, lr=0.001):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None

    def fit(self, X, y):
        self.classes_ = np.unique(y)
        
        # Dynamically set input_size based on X if not provided correctly
        actual_input_size = X.shape[-1]
        
        self.model = FormTrackerGRU(
            input_size=actual_input_size, 
            hidden_size=self.hidden_size,
            num_layers=self.num_layers
        ).to(self.device)
        
        self.criterion = nn.CrossEntropyLoss()
        self.optimizer = optim.Adam(self.model.parameters(), lr=self.lr)
        
        # Reshape X to (samples, seq_length, features) if it's 2D
        # In a full pipeline, feature engineering should output 3D sequences.
        # Here we add a dummy sequence dimension if needed for compatibility.
        if len(X.shape) == 2:
            X_seq = np.expand_dims(X, axis=1)
        else:
            X_seq = X
            
        dataset = MatchSequenceDataset(X_seq, y)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        
        self.model.train()
        for epoch in range(self.epochs):
            for batch_X, batch_y in loader:
                batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)
                
                self.optimizer.zero_grad()
                outputs = self.model(batch_X)
                loss = self.criterion(outputs, batch_y)
                loss.backward()
                self.optimizer.step()
                
        return self

    def predict_proba(self, X):
        if self.model is None:
            raise Exception("Model is not fitted yet.")
            
        if len(X.shape) == 2:
            X_seq = np.expand_dims(X, axis=1)
        else:
            X_seq = X
            
        dataset = MatchSequenceDataset(X_seq)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=False)
        
        self.model.eval()
        all_probs = []
        with torch.no_grad():
            for batch_X in loader:
                batch_X = batch_X.to(self.device)
                outputs = self.model(batch_X)
                probs = torch.softmax(outputs, dim=1).cpu().numpy()
                all_probs.append(probs)
                
        return np.vstack(all_probs)
        
    def predict(self, X):
        probs = self.predict_proba(X)
        return np.argmax(probs, axis=1)

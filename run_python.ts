import { execSync } from 'child_process';

try {
  console.log("Installing python dependencies...");
  execSync('pip install pandas numpy scikit-learn xgboost requests joblib torch', { stdio: 'inherit' });
  console.log("Running backtest...");
  execSync('python3 ml/backtest.py', { stdio: 'inherit' });
} catch (e) {
  console.error(e);
}

import { execSync } from 'child_process';

try {
  console.log("Checking python3...");
  execSync('python3 --version', { stdio: 'inherit' });
  console.log("Checking pip3...");
  execSync('pip3 --version', { stdio: 'inherit' });
} catch (e) {
  console.error(e);
}

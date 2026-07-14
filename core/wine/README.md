## Adding the APT repository

```bash
# 1. Enable i386 architecture (Wine needs 32-bit libraries)
sudo dpkg --add-architecture i386
sudo apt-get update

# 2. Install tools needed to add the repository
sudo apt-get install -y curl gnupg

# 3. Add the repository GPG key
#    If this step is skipped or the key file is empty, apt will report:
#    "Missing key ... The repository is not signed".
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://cusdeb-com.github.io/os/KEY.gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/cusdeb-os.gpg
sudo chmod 644 /etc/apt/keyrings/cusdeb-os.gpg

# 4. Add the APT source
echo "deb [signed-by=/etc/apt/keyrings/cusdeb-os.gpg] https://cusdeb-com.github.io/os/ stable main" \
  | sudo tee /etc/apt/sources.list.d/cusdeb-os.list

# 5. Install wine
sudo apt-get update
sudo apt-get install -y wine
```

#!/bin/bash
# Commands to push to GitHub
# Replace YOUR_USERNAME with your actual GitHub username

cd "/Users/anshmansingh/Desktop/ojt 3 try"

# Add remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/catalog-image-pipeline.git

# Push to GitHub
git push -u origin main

echo "✅ Code pushed to GitHub!"
echo "Repository: https://github.com/YOUR_USERNAME/catalog-image-pipeline"


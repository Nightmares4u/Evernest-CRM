# GitHub Setup

## 1. Create repo locally

```bash
cd evernest-crm-starter
git init
git add .
git commit -m "Initial CRM blueprint and starter structure"
```

## 2. Create remote repo on GitHub

Name suggestion: `evernest-crm`

## 3. Connect remote

```bash
git remote add origin git@github.com:YOUR_USERNAME/evernest-crm.git
git branch -M main
git push -u origin main
```

## 4. Create dev branch

```bash
git checkout -b dev
git push -u origin dev
```

## 5. Start feature branches

Example:

```bash
git checkout dev
git checkout -b feat/backend-bootstrap
```

## 6. Working rule

- never code directly on `main`
- prefer one feature branch per module
- keep commits small
- merge into `dev` first
- merge `dev` into `main` only after testing

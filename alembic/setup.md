# Alembic Integration Setup Guide

This guide explains how to integrate the Alembic migration files into your existing LLM Search Backend project.

## 📁 File Placement

Place these files in your project as follows:

```
llm-search-backend/
├── alembic/                              # 📁 NEW: Create this directory
│   ├── versions/                         # 📁 NEW: Migration scripts directory
│   │   └── 001_20241201_0000_initial_tables.py  # 📄 NEW: Initial migration
│   ├── env.py                           # 📄 NEW: Alembic environment config
│   ├── script.py.mako                   # 📄 NEW: Migration template
│   └── README                           # 📄 NEW: Migration documentation
├── alembic.ini                          # 📄 NEW: Alembic configuration
├── scripts/
│   ├── manage_migrations.py             # 📄 NEW: Migration management script
│   └── ... (existing scripts)
├── app/                                 # ✅ EXISTING: Your app directory
│   ├── database/
│   │   ├── models.py                    # ✅ EXISTING: Updated models
│   │   └── ...
│   └── ...
└── ... (existing files)
```

## 🚀 Setup Steps

### 1. Create the Directory Structure

```bash
# Create the alembic directory
mkdir -p alembic/versions

# Create the migration management script directory if needed
mkdir -p scripts
```

### 2. Add the Files

Copy all the provided files to their respective locations:

- `alembic.ini` → project root
- `alembic/env.py` → alembic directory
- `alembic/script.py.mako` → alembic directory
- `alembic/README` → alembic directory
- `alembic/versions/001_20241201_0000_initial_tables.py` → alembic/versions directory
- `scripts/manage_migrations.py` → scripts directory

### 3. Make the Migration Script Executable

```bash
chmod +x scripts/manage_migrations.py
```

### 4. Update Requirements (if needed)

Ensure your `requirements.txt` includes Alembic:

```txt
alembic==1.12.1
```

### 5. Configure Environment Variables

Update your `.env` file to ensure the database URL is set:

```bash
DATABASE_URL=postgresql+asyncpg://searchuser:searchpass@localhost:5432/searchdb
```

## 🔧 Initial Setup

### Option 1: Fresh Database Setup

If you're starting with a fresh database:

```bash
# Initialize database with migrations
make db-init

# Or using the script directly
python scripts/manage_migrations.py init
```

### Option 2: Existing Database Setup

If you already have tables created by SQLAlchemy:

```bash
# Stamp the database with the initial migration (without running it)
make db-stamp REV=001_initial_tables

# Or using the script directly
python scripts/manage_migrations.py stamp 001_initial_tables
```

## 🧪 Test the Setup

### 1. Check Migration Status

```bash
make db-status
# Should show: Current revision: 001_initial_tables
```

### 2. Create a Test Migration

```bash
make db-migrate
# Enter message: "test migration"
# Should create a new migration file in alembic/versions/
```

### 3. Validate Migrations

```bash
make db-validate
# Should show no errors
```

## 🐳 Docker Integration

The Docker setup already includes the alembic files. The migration commands work in Docker:

```bash
# Initialize database in Docker
make docker-up
make db-init-docker

# Run migrations in Docker
docker-compose exec api python scripts/manage_migrations.py upgrade

# Create migration in Docker
docker-compose exec api python scripts/manage_migrations.py create "add new feature"
```

## 📝 Common Commands

After setup, use these commands for database management:

```bash
# Create new migration
make db-migrate

# Apply migrations
make db-upgrade

# Check status
make db-status

# View history
make db-history

# Downgrade (careful!)
make db-downgrade REV=-1
```

## 🔍 Verification

To verify everything is working correctly:

1. **Check Alembic is working:**
   ```bash
   alembic current
   ```

2. **Check database connection:**
   ```bash
   python scripts/manage_migrations.py current
   ```

3. **Test creating a migration:**
   ```bash
   python scripts/manage_migrations.py create "test_migration"
   ```

4. **Validate the generated migration:**
   ```bash
   python scripts/manage_migrations.py validate
   ```

## 🚨 Important Notes

1. **Backup First:** Always backup your database before running migrations in production
2. **Review Migrations:** Always review auto-generated migrations before applying them
3. **Test Thoroughly:** Test migrations on a copy of production data
4. **Environment Variables:** Ensure `DATABASE_URL` is correctly set in all environments

## 🆘 Troubleshooting

### Alembic Command Not Found
```bash
pip install alembic==1.12.1
```

### Database Connection Issues
```bash
# Check your DATABASE_URL
echo $DATABASE_URL

# Test database connection
python scripts/manage_migrations.py current
```

### Migration Conflicts
```bash
# If you have migration conflicts, merge them:
alembic merge -m "merge migrations" heads
```

### Reset Migrations (Development Only)
```bash
# WARNING: This will drop all data
make db-stamp REV=base
make db-upgrade
```

## ✅ Success!

Once setup is complete, you'll have:

- ✅ Full database migration support
- ✅ Version-controlled schema changes
- ✅ Easy rollback capabilities
- ✅ Team collaboration on database changes
- ✅ Production-ready deployment process

Your database changes are now fully managed and version-controlled! 🎉

# Development Scripts

Local development and testing utilities for SWE Agent.

## 🚀 Server Management (`servers.sh`)

Manage UI and API servers for local development.

```bash
scripts/servers.sh [start|stop|restart|status]
```

**Commands:**

- `start` - Start UI (8001) and API (8002) servers in background
- `stop` - Stop both servers gracefully
- `restart` - Restart both servers
- `status` - Show server status and health

**Quick URLs:**

- UI: http://127.0.0.1:8001
- API: http://127.0.0.1:8002
- Agents Catalogue: http://127.0.0.1:8001/agents-catalogue
- API Docs: http://127.0.0.1:8002/docs

## 🗄️ Database Setup (`setup_database.sh`)

Initialize MySQL database for SWE Agent.

```bash
scripts/setup_database.sh
```

**What it does:**

- Creates `swe_agent` database
- Sets up `swe_agent` user with password
- Configures proper permissions
- Uses UTF8MB4 charset for full Unicode support

**Requirements:**

- MySQL server installed and running
- Root MySQL access

## ⚠️ Production Note

These scripts are for **local development only**. For production:

- Use Docker Compose
- Use `commands/` directory scripts
- Use proper process managers (systemd, supervisord)

#!/usr/bin/env python3
# ./setup.py
"""
Setup script for Robinhood Crypto Trading App
Helps with initial configuration and testing
"""

import os

# import sys
import json
import getpass
from pathlib import Path


# pylint:disable=broad-exception-caught,logging-fstring-interpolation,missing-module-docstring,line-too-long, unspecified-encoding


def create_directories():
    """Create necessary directories"""
    directories = ["logs"]

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✓ Created directory: {directory}")


def setup_config():
    """Interactive configuration setup"""
    print("\n=== Robinhood Crypto Trading App Configuration ===")
    print("This will help you set up your configuration file.")
    print("You can also manually edit config.json later.\n")

    # Load existing config if it exists
    config_file = "config.json"
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            config = json.load(f)
        print("Found existing config.json, updating...")
    else:
        # Default configuration
        config = {
            "robinhood": {"username": "", "password": ""},
            "database": {"path": "crypto_trading.db"},
            "historical_data": {
                "days_back": 60,
                "interval_minutes": 5,
                "buffer_days": 1,
            },
            "logging": {
                "level": "INFO",
                "file_path": "logs/app.log",
                "max_file_size_mb": 10,
                "backup_count": 5,
            },
            "retry": {"max_attempts": 3, "backoff_factor": 2, "initial_delay": 1},
        }

    # Get Robinhood credentials
    print("1. Robinhood Credentials")
    username = input(f"Username [{config['robinhood']['username']}]: ").strip()
    if username:
        config["robinhood"]["username"] = username

    if not config["robinhood"]["username"]:
        print("⚠️  Username is required")
        config["robinhood"]["username"] = input("Username: ").strip()

    password = getpass.getpass("Password (hidden): ").strip()
    if password:
        config["robinhood"]["password"] = password

    if not config["robinhood"]["password"]:
        print("⚠️  Password is required")
        config["robinhood"]["password"] = getpass.getpass("Password: ").strip()

    # Historical data settings
    print("\n2. Historical Data Settings")
    days_back = input(
        f"Days of historical data to fetch initially [{config['historical_data']['days_back']}]: "
    ).strip()
    if days_back.isdigit():
        config["historical_data"]["days_back"] = int(days_back)

    interval = input(
        f"Data interval in minutes [{config['historical_data']['interval_minutes']}]: "
    ).strip()
    if interval.isdigit():
        config["historical_data"]["interval_minutes"] = int(interval)

    buffer = input(
        f"Buffer days for incremental updates [{config['historical_data']['buffer_days']}]: "
    ).strip()
    if buffer.isdigit():
        config["historical_data"]["buffer_days"] = int(buffer)

    # Logging settings
    print("\n3. Logging Settings")
    log_level = (
        input(f"Log level (DEBUG/INFO/WARNING/ERROR) [{config['logging']['level']}]: ")
        .strip()
        .upper()
    )
    if log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
        config["logging"]["level"] = log_level

    # Save configuration
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n✓ Configuration saved to {config_file}")

    # Security reminder
    print("\n🔐 Security Reminder:")
    print("- Consider using environment variables for credentials:")
    print("  export ROBINHOOD_USERNAME='your_username'")
    print("  export ROBINHOOD_PASSWORD='your_password'")
    print("- Restrict file permissions on config.json")
    print("- Add config.json to .gitignore if using version control")


def create_env_example():
    """Create .env.example file"""
    env_content = """# Robinhood Crypto Trading App Environment Variables
# Copy this file to .env and fill in your actual credentials

ROBINHOOD_USERNAME=your_username_here
ROBINHOOD_PASSWORD=your_password_here
"""

    with open(".env.example", "w") as f:
        f.write(env_content)

    print("✓ Created .env.example file")


def create_gitignore():
    """Create .gitignore file"""
    gitignore_content = """# Robinhood Crypto Trading App
# Ignore sensitive and generated files

# Configuration files with credentials
config.json
.env

# Database files
*.db
*.sqlite
*.sqlite3

# Log files
logs/
*.log

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
"""

    with open(".gitignore", "w") as f:
        f.write(gitignore_content)

    print("✓ Created .gitignore file")


def test_imports():
    """Test if required packages can be imported"""
    print("\n=== Testing Dependencies ===")

    required_packages = [
        ("robin_stocks", "robin-stocks"),
        ("sqlalchemy", "sqlalchemy"),
        ("dotenv", "python-dotenv"),
    ]

    missing_packages = []

    for package, pip_name in required_packages:
        try:
            __import__(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} (install with: pip install {pip_name})")
            missing_packages.append(pip_name)

    if missing_packages:
        print(f"\n⚠️  Missing packages. Install with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    else:
        print("\n✓ All dependencies are available")
        return True


def show_next_steps():
    """Show next steps after setup"""
    print("\n=== Next Steps ===")
    print("1. Install missing dependencies (if any):")
    print("   pip install -r requirements.txt")
    print("\n2. Test the application:")
    print("   python main.py")
    print("\n3. Set up scheduled execution:")
    print("   - Linux: Add to crontab")
    print("   - Windows: Use Task Scheduler")
    print("\n4. Monitor logs:")
    print("   - Check logs/app.log for detailed information")
    print("   - Console shows summary information")
    print("\n5. Database:")
    print("   - SQLite database will be created automatically")
    print("   - Use any SQLite browser to view data")


def main():
    """Main setup function"""
    print("🚀 Robinhood Crypto Trading App Setup")
    print("=====================================")

    # Create directories
    print("\n--- Creating Directories ---")
    create_directories()

    # Test dependencies
    deps_ok = test_imports()

    # Setup configuration
    if deps_ok:
        setup_config()
    else:
        print("\n⚠️  Please install missing dependencies before configuring")

    # Create helper files
    print("\n--- Creating Helper Files ---")
    create_env_example()
    create_gitignore()

    # Show next steps
    show_next_steps()

    print("\n🎉 Setup completed!")


if __name__ == "__main__":
    main()

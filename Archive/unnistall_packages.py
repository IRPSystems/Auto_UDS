import os
import time
import subprocess
import pkg_resources
from datetime import datetime, timedelta

# How many days back to check
days = 2
cutoff = time.time() - (days * 86400)

# Get site-packages path
site_packages = next(p for p in pkg_resources.working_set).location

# Find recently modified package folders
recent = []
for dist in pkg_resources.working_set:
    dist_path = os.path.join(site_packages, dist.project_name.replace("-", "_"))
    if os.path.exists(dist_path) and os.path.getmtime(dist_path) > cutoff:
        recent.append(dist.project_name)

if not recent:
    print(f"No packages installed in the last {days} days.")
else:
    print(f"The following packages were installed in the last {days} days:\n")
    for name in recent:
        print(f" - {name}")

    confirm = input("\nDo you want to uninstall them all? (yes/no): ").strip().lower()
    if confirm == "yes":
        for name in recent:
            subprocess.call(["pip", "uninstall", "-y", name])
        print("✅ Uninstallation complete.")
    else:
        print("❌ Uninstallation cancelled.")

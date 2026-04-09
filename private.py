from huggingface_hub import HfApi
from datetime import datetime, timezone

# --- Target Configuration ---
TARGET_AUTHOR = "Aasdfip" 
TARGET_DATE = datetime(2026, 2, 10, tzinfo=timezone.utc) 
DATE_METRIC = "created_at" # or "lastModified"

def lock_recent_datasets():
    api = HfApi()
    datasets = api.list_datasets(author=TARGET_AUTHOR, full=True)
    
    for ds in datasets:
        ds_date = getattr(ds, DATE_METRIC, None)
        # Check if dataset exists, has the date metric, and is strictly newer than target
        if ds_date and ds_date > TARGET_DATE:
            print(f"Locking down {ds.id}...")
            api.update_repo_visibility(repo_id=ds.id, private=True, repo_type="dataset")
lock_recent_datasets()
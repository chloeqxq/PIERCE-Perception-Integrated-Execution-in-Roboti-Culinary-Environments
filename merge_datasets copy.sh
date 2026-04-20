# Merge train and validation splits back into one dataset
lerobot-edit-dataset \
    --repo_id=Aasdfip/target_train \
    --operation.type=merge \
    --operation.repo_ids="['Aasdfip/skewer_foam_04_17_0', 'Aasdfip/gather_all','Aasdfip/gather_blue','Aasdfip/gather_green','Aasdfip/gather_white']" \
    --push_to_hub=true 
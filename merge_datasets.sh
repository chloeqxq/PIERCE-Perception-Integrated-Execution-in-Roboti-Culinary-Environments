# Merge train and validation splits back into one dataset
lerobot-edit-dataset \
    --repo_id=Aasdfip/curated_pretrain \
    --operation.type=merge \
    --operation.repo_ids="['Aasdfip/full_skewer','Aasdfip/box_pretrain_2','Aasdfip/box_pretrain','Aasdfip/skewer_pretrain','Aasdfip/skewer_pretrain_2','Aasdfip/tidy_pretrain','Aasdfip/skewer_foam_04_18_0','Aasdfip/skewer_foam_04_18_1','Aasdfip/skewer_foam_04_17_0', 'Aasdfip/gather_all','Aasdfip/gather_blue','Aasdfip/gather_green','Aasdfip/gather_white']" \
    --push_to_hub=true 
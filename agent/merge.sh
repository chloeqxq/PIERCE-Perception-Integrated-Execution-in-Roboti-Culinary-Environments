# Merge train and validation splits back into one dataset                                                                       
lerobot-edit-dataset \
    --repo_id=Aasdfip/task_pretrain \
    --operation.type=merge \
    --operation.repo_ids="['Aasdfip/subtask_test','Aasdfip/subtask_04_21','Aasdfip/subtask_04_21_1','Aasdfip/subtask_pick_skew']" \
    --push_to_hub=true  
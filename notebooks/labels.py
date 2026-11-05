import pandas as pd
import ast

CLASSES = ["NORM", "MI", "STTC", "CD", "HYP"]

def prepare_labels(database_path, statements_path):

    df = pd.read_csv(database_path)
    scp = pd.read_csv(statements_path, index_col=0)

    df["scp_dict"] = df["scp_codes"].apply(ast.literal_eval)

    scp_final = scp[(scp["diagnostic"] == 1) & (scp["diagnostic_class"].notna())]
    def get_superclass(scp_codes):
        classes = set()
        for scp_code in scp_codes.keys():
            if scp_code in scp_final.index:
                classes.add(scp_final.loc[scp_code, "diagnostic_class"])

        return sorted(classes)

    df["scp_class"] = df["scp_dict"].apply(get_superclass)

    all_classes = list(scp_final["diagnostic_class"].unique())
    assert set(all_classes) == set(CLASSES)

    for class_name in CLASSES:
        df[class_name] = df["scp_class"].apply(lambda x: int(class_name in x))

    labels_df = df[["ecg_id", "patient_id", "strat_fold"] + CLASSES].copy()

    labels_df["n_labels"] = labels_df[CLASSES].sum(axis=1)
    labels_df["has_target_label"] = labels_df["n_labels"] > 0

    return labels_df

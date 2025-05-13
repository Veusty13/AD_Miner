import os
import zipfile
import json
import shutil

source_dir = "../bloodhound-automation/data/goadV2/"
target_dir = "../bloodhound-automation/data/goadV2_1/"

vulnerable_nodes = {
    "SPYS@ESSOS.LOCAL",
    "JORAH.MORMONT@ESSOS.LOCAL",
    "DOMAIN USERS@ESSOS.LOCAL",
    "DOMAIN ADMINS@ESSOS.LOCAL",
    "DAENERYS.TARGARYEN@ESSOS.LOCAL",
    "ACROSSTHENARROWSEA@SEVENKINGDOMS.LOCAL",
    "KINGSLANDING.SEVENKINGDOMS.LOCAL",
    "ENTERPRISE ADMINS@SEVENKINGDOMS.LOCAL",
    "DOMAIN ADMINS@NORTH.SEVENKINGDOMS.LOCAL",
    "DOMAIN ADMINS@SEVENKINGDOMS.LOCAL",
    "SERVER OPERATORS@ESSOS.LOCAL",
    "MEEREEN.ESSOS.LOCAL",
    "ACCOUNT OPERATORS@ESSOS.LOCAL",
    "KHAL.DROGO@ESSOS.LOCAL",
    "PRINT OPERATORS@ESSOS.LOCAL",
    "BACKUP OPERATORS@ESSOS.LOCAL",
    "ENTERPRISE DOMAIN CONTROLLERS@ESSOS.LOCAL",
    "BRAAVOS.ESSOS.LOCAL",
    "VAGRANT@ESSOS.LOCAL",
    "SMALL COUNCIL@SEVENKINGDOMS.LOCAL",
    "DRAGONSTONE@SEVENKINGDOMS.LOCAL",
    "KINGSGUARD@SEVENKINGDOMS.LOCAL",
    "STANNIS.BARATHEON@SEVENKINGDOMS.LOCAL",
    "TYRON.LANNISTER@SEVENKINGDOMS.LOCAL",
    "VISERYS.TARGARYEN@ESSOS.LOCAL",
}

vulnerable_edges = {
    "MemberOf",
    "GenericAll",
    "ADCSESC1",
    "Contains",
    "DCSync",
    "WriteDacl",
    "CanExtractDCSecrets",
    "ADCSESC4",
    "CanLoadCode",
    "GoldenCert",
    "AddMember",
    "WriteOwner",
    "AddSelf",
    "Owns",
    "SQLAdmin",
    "GPLink",
    "CanLogOnLocallyOnDC",
    "GenericWrite",
    "ForceChangePassword",
}

if not os.path.exists(target_dir):
    os.makedirs(target_dir)


def clean_json_data(data):
    nodes_to_remove = set()
    edges_to_remove = set()

    for node in data.get("nodes", []):
        if node["label"] in vulnerable_nodes:
            nodes_to_remove.add(node["id"])

    data["nodes"] = [
        node for node in data["nodes"] if node["id"] not in nodes_to_remove
    ]

    for edge in data.get("edges", []):
        if (
            edge["source"] in nodes_to_remove
            or edge["target"] in nodes_to_remove
            or edge["label"] in vulnerable_edges
        ):
            edges_to_remove.add(edge["id"])

    data["edges"] = [
        edge for edge in data["edges"] if edge["id"] not in edges_to_remove
    ]

    return data


for file in os.listdir(source_dir):
    source_file = os.path.join(source_dir, file)
    target_file = os.path.join(target_dir, file)

    if file.endswith(".zip"):
        with zipfile.ZipFile(source_file, "r") as zin:
            with zipfile.ZipFile(target_file, "w") as zout:
                for item in zin.infolist():
                    with zin.open(item) as f:
                        if item.filename.endswith(".json"):
                            data = json.load(f)
                            cleaned_data = clean_json_data(data)
                            zout.writestr(item.filename, json.dumps(cleaned_data))
                        else:
                            zout.writestr(item.filename, f.read())
    elif file.endswith(".json"):
        with open(source_file, "r") as f:
            data = json.load(f)
        cleaned_data = clean_json_data(data)
        with open(target_file, "w") as f:
            json.dump(cleaned_data, f)
    else:
        shutil.copy2(source_file, target_file)

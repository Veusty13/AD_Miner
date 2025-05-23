import json
import os

input_dir = "../bloodhound-automation/data/goadV2/"
output_dir = "../bloodhound-automation/data/goadV2_1/"
os.makedirs(output_dir, exist_ok=True)
input_path = os.path.join(input_dir, "ESSOS_NORTH_SEVENKINGDOMS_concat_all_entities.json")
output_path = os.path.join(output_dir, "ESSOS_NORTH_SEVENKINGDOMS_concat_all_entities.json")

with open(input_path, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

data = {}
for key, content in raw_data.items():
    parts = key.split("_")
    if len(parts) < 3:
        continue
    region = parts[0].upper()
    category = parts[-1]
    data.setdefault(region, {}).setdefault(category, {"data": [], "meta": {}})
    data[region][category]["data"].extend(content.get("data", []))
    meta = {k: v for k, v in content.get("meta", {}).items() if k != "type"}
    if data[region][category]["meta"]:
        for mk, mv in meta.items():
            if mk not in ("count",) and mk not in data[region][category]["meta"]:
                data[region][category]["meta"][mk] = mv
    else:
        data[region][category]["meta"] = meta

moves = []
for region, cats in list(data.items()):
    for category, cat_content in cats.items():
        cleaned = []
        for item in cat_content["data"]:
            if not isinstance(item, dict):
                continue
            props = item.setdefault("Properties", {})
            domain = props.get("domain")
            if isinstance(domain, str):
                props["domain"] = domain.upper()
                domain_region = domain.split(".")[0].upper()
                if domain_region and domain_region != region:
                    moves.append((region, domain_region, category, item))
                    continue
            if "IsACLProtected" in item:
                if props.get("isaclprotected") is None:
                    props["isaclprotected"] = item["IsACLProtected"]
                item.pop("IsACLProtected", None)
            if "DomainSID" in item:
                if props.get("domainsid") is None:
                    props["domainsid"] = item["DomainSID"]
                item.pop("DomainSID", None)
            cleaned.append(item)
        data[region][category]["data"] = cleaned

for src, tgt, category, item in moves:
    data.setdefault(tgt, {}).setdefault(category, {"data": [], "meta": {}})
    tgt_list = data[tgt][category]["data"]
    obj_id = item.get("ObjectIdentifier")
    dn = item.get("Properties", {}).get("distinguishedname")
    if not any((obj_id and obj_id == it.get("ObjectIdentifier")) or
               (dn and dn == it.get("Properties", {}).get("distinguishedname"))
               for it in tgt_list):
        tgt_list.append(item)

for region, cats in data.items():
    for category, cat_content in cats.items():
        cat_content["meta"]["count"] = len(cat_content["data"])

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

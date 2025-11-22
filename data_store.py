# data_store.py

import json
import os
from typing import List, Dict, Any
from config import DATA_FILE

# Default prices (admin panel se change ho sakte)
DEFAULT_PRICES = {
    "1000": 40.0,
    "2000": 70.0,
    "4000": 140.0,
}


def _default_data() -> Dict[str, Any]:
    return {
        "vouchers": {"1000": [], "2000": [], "4000": []},
        "orders": [],        # list of dict
        "users": [],         # list of telegram user_ids
        "prices": DEFAULT_PRICES.copy(),
    }


def load_data() -> Dict[str, Any]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = _default_data()
    else:
        data = _default_data()

    # ensure all keys exist
    base = _default_data()
    for k, v in base.items():
        if k not in data:
            data[k] = v
    for d, price in DEFAULT_PRICES.items():
        data["vouchers"].setdefault(d, [])
        data["prices"].setdefault(d, price)
    return data


DATA = load_data()


def save_data() -> None:
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(DATA, f, indent=2)
    except Exception as e:
        print("Error saving data:", e)


# ---------- USERS ----------

def add_user(user_id: int) -> None:
    if user_id not in DATA["users"]:
        DATA["users"].append(user_id)
        save_data()


def get_users() -> List[int]:
    return DATA["users"]


# ---------- PRICES ----------

def get_price(denom: int) -> float:
    return float(DATA["prices"].get(str(denom), 0.0))


def set_price(denom: int, new_price: float) -> None:
    DATA["prices"][str(denom)] = float(new_price)
    save_data()


# ---------- VOUCHERS ----------

def vouchers_for(denom: int) -> List[str]:
    return DATA["vouchers"].get(str(denom), [])


def add_vouchers(denom: int, codes: List[str]) -> None:
    lst = vouchers_for(denom)
    lst.extend(codes)
    DATA["vouchers"][str(denom)] = lst
    save_data()


def pop_voucher(denom: int):
    lst = vouchers_for(denom)
    if not lst:
        return None
    code = lst.pop(0)
    DATA["vouchers"][str(denom)] = lst
    save_data()
    return code


def stock_text() -> str:
    return (
        "📦 *Current Stock*\n"
        f"• ₹1000: {len(vouchers_for(1000))} vouchers\n"
        f"• ₹2000: {len(vouchers_for(2000))} vouchers\n"
        f"• ₹4000: {len(vouchers_for(4000))} vouchers"
    )


# ---------- ORDERS ----------

def add_order(order: Dict[str, Any]) -> None:
    DATA["orders"].append(order)
    save_data()


def update_order(order_id: str, **fields) -> None:
    for o in DATA["orders"]:
        if o.get("order_id") == order_id:
            o.update(fields)
            save_data()
            break


def list_orders(limit: int = 10) -> List[Dict[str, Any]]:
    return DATA["orders"][-limit:]

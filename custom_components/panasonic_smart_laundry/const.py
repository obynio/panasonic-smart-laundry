"""Constants for the Panasonic Smart Laundry integration."""

DOMAIN = "panasonic_smart_laundry"

CONF_COM_ID = "com_id"
CONF_APPLIANCE_ID = "appliance_id"

DEFAULT_COM_ID = "NA-VX9800"

SUPPORTED_COM_IDS: tuple[str, ...] = (
    "NA-F10AKE3",
    "NA-F10AKE4",
    "NA-F10AKE5",
    "NA-F8AKE3",
    "NA-F8AKE4",
    "NA-F8AKE5",
    "NA-F9AKE3",
    "NA-F9AKE4",
    "NA-F9AKE5",
    "NA-FA10K2",
    "NA-FA10K3",
    "NA-FA10K5",
    "NA-FA11K1",
    "NA-FA11K2",
    "NA-FA11K3",
    "NA-FA11K5",
    "NA-FA12V1",
    "NA-FA12V2",
    "NA-FA12V3",
    "NA-FA12V5",
    "NA-FA12V6",
    "NA-FA8K2",
    "NA-FA8K3",
    "NA-FA8K5",
    "NA-FA9K2",
    "NA-FA9K3",
    "NA-FA9K5",
    "NA-FW10K1",
    "NA-FW10K2",
    "NA-LX127A",
    "NA-LX127B",
    "NA-LX127C",
    "NA-LX127D",
    "NA-LX127E",
    "NA-LX129A",
    "NA-LX129B",
    "NA-LX129C",
    "NA-LX129D",
    "NA-LX129E",
    "NA-SD10UA",
    "NA-SD10UB",
    "NA-VG1200",
    "NA-VG1300",
    "NA-VG1400",
    "NA-VG1500",
    "NA-VG2200",
    "NA-VG2300",
    "NA-VG2400",
    "NA-VG2500",
    "NA-VG2600",
    "NA-VG2700",
    "NA-VG2800",
    "NA-VG2900",
    "NA-VX900A",
    "NA-VX900B",
    "NA-VX9800",
    "NA-VX9900",
)

SCAN_INTERVAL = 60

API_BASE_URL = "https://app.wad.apws.panasonic.com"
AUTH_URL = "https://auth.digital.panasonic.com"
CLIENT_ID = "2wSeRcOi0MoAv5ByV1tSUusr5VW3CP4v"
AUTH0_CLIENT = (
    "eyJuYW1lIjoiQXV0aDAuQW5kcm9pZCIsImVudiI6eyJhbmRyb2lkIjoiMzMifSwidmVyc2lvbiI6IjIuOC4wIn0="
)
TOKEN_REFRESH_BUFFER = 300
REDIRECT_URI = (
    "auth0://auth.digital.panasonic.com/android/com.panasonic.SmartLaundry/callback"
)
OAUTH_SCOPE = "openid offline_access smartlaundry.control offline_access"
OAUTH_AUDIENCE = f"https://club.panasonic.jp/{CLIENT_ID}/api/v1/"

OPERATION_KEYS = {
    "00": "idle",
    "01": "washing",
    "03": "rinsing",
    "05": "spinning",
    "06": "drying",
    "07": "fluffing",
    "08": "soft_keep",
    "0C": "paused",
    "12": "filter_due",
    "13": "reservation_waiting",
    "EF": "finished",
}

TRANSITION_KEYS = {
    "41": "running_wash",
    "42": "running_rinse",
    "43": "running_spin",
    "44": "paused",
    "45": "finished_wash_only",
    "51": "finished_dry",
    "52": "running_dry",
    "54": "finished_soft_keep",
    "61": "standby",
    "EF": "finished",
}
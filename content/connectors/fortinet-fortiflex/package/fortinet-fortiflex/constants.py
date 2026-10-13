"""
Copyright start
MIT License
Copyright (c) 2023 Fortinet Inc
Copyright end
"""

PRODUCT_ID = {
    "FortiGate Virtual Machine - Service Bundle": 1,
    "FortiManager Virtual Machine": 2,
    "FortiWeb Virtual Machine - Service Bundle": 3,
    "FortiGate Virtual Machine - A La Carte Services": 4,
    "FortiClient EMS On-Prem": 5,
    "FortiAnalyzer Virtual Machine": 7,
    "FortiPortal Virtual Machine": 8,
    "FortiADC Virtual Machine": 9,
    "FortiSOAR Virtual Machine": 10,
    "FortiMail Virtual Machine": 11,
    "FortiNAC Virtual Machine": 12,
    "FortiGate Hardware": 101,
    "FortiAP Hardware": 102,
    "FortiSwitch Hardware": 103,
    "FortiWeb Cloud - Private": 202,
    "FortiWeb Cloud - Public": 203,
    "FortiClient EMS Cloud": 204,
    "FortiSASE": 205,
    "FortiEDR": 206,
    "FortiNDR Cloud": 207,
    "FortiRecon": 208,
    "FortiSIEM Cloud": 209
}

CPU_SIZE = {
    "1 CPU": "1",
    "2 CPUs": "2",
    "4 CPUs": "4",
    "8 CPUs": "8",
    "16 CPUs": "16",
    "32 CPUs": "32",
    "Unlimited CPUs": "2147483647"
}

SERVICE_PACKAGE = {
    "FortiCare": "FC",
    "UTP": "UTP",
    "Enterprise": "ENT",
    "ATP": "ATP",
    "Standard": "FWBSTD",
    "Advanced": "FWBADV"
}

SERVICE_PACKAGE_FOR_FG_HD = {
    "FortiCare Premium": "FGHWFC247",
    "FortiCare Elite": "FGHWFCEL",
    "ATP": "FGHWATP",
    "UTP": "FGHWUTP",
    "Enterprise": "FGHWENT"
}

SUPPORT_SERVICES_FG = {
    "FortiCare Premium": "FC247",
    "FortiCare Elite": "ASET"
}

SUPPORT_SERVICES_FOR_FC_EMS = {
    "FortiCare Premium": "FCTFC247"
}

SUPPORT_SERVICES_FOR_FAZ = {
    "FortiCare Premium": "FAZFC247"
}

SUPPORT_SERVICES_FOR_ADC = {
    "Standard": "FDVSTD",
    "Advanced": "FDVADV",
    "FortiCare Premium": "FDVFC247"
}

FORTIGUARD_SERVICE = {
    "Intrusion Prevention": "IPS",
    "Advanced Malware": "AVDB",
    "Security Rating": "FGSA",
    "DLP": "DLDB",
    "AI-Based InLine Sandbox": "FAIS",
    "Web, DNS & Video Filtering": "FURLDNS"
}

CLOUD_SERVICE = {
    "FortiGate Cloud": "FAMS",
    "SD-WAN Underlay": "SWNM",
    "FortiAnalyzer Cloud with SOCaaS": "AFAC",
    "FortiAnalyzer Cloud": "FAZC"
}

ADDONS = {
    "FortiCare Best Practice": "BPS"
}

ADDONS_FOR_FG_HD = {
    "FortiCare Elite Upgrade": "FGHWFCELU",
    "FortiGate Cloud Management": "FGHWFAMS",
    "AI-Based In-line Sandbox": "FGHWFAIS",
    "SD-WAN Underlay": "FGHWSWNM",
    "FortiGuard DLP": "FGHWDLDB",
    "FortiAnalyzer Cloud": "FGHWFAZC",
    "SOCaaS": "FGHWSOCA",
    "Managed FortiGate": "FGHWMGAS",
    "SD-WAN Connector for FortiSASE": "FGHWSPAL",
    "FortiConverter Service": "FGHWFCSS"
}

DEVICE_MODEL = {
    "FortiGate-40F": "FGT40F",
    "FortiGate-60F": "FGT60F",
    "FortiGate-70F": "FGT70F",
    "FortiGate-80F": "FGT80F",
    "FortiGate-100F": "FG100F",
    "FortiGate-60E": "FGT60E",
    "FortiGate-61F": "FGT61F",
    "FortiGate-100E": "FG100E",
    "FortiGate-101F": "FG101F",
    "FortiGate-200E": "FG200E",
    "FortiGate-200F": "FG200F",
    "FortiGate-201F": "FG201F",
    "FortiGate-400F": "FG4H0F",
    "FortiGate-600F": "FG6H0F",
    "FortiWifi-40F": "FWF40F",
    "FortiWifi-60F": "FWF60F",
    "FortiGateRugged-60F": "FGR60F",
    "FortiGateRugged-70F": "FR70FB",
    "FortiGate-81F": "FGT81F",
    "FortiGate-101E": "FG101E",
    "FortiGate-401F": "FG4H1F",
    "FortiGate-1000F": "FG1K0F",
    "FortiGate-1800F": "FG180F",
    "FortiGate-2600F": "F2K60F",
    "FortiGate-3000F": "FG3K0F",
    "FortiGate-3001F": "FG3K1F",
    "FortiGate-3200F": "FG3K2F"
}

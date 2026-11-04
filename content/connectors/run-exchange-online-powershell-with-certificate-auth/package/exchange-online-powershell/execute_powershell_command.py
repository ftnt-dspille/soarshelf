import subprocess
import json
import os
import re
from connectors.core.connector import get_logger, ConnectorError

logger = get_logger('exchange-online-powershell')

def execute_powershell_command(config, params):
    # 1. Retrieve Global Config
    app_id = config.get('appID')
    cert_path = config.get('certificatePath')
    org = config.get('organization')

    # 2. Retrieve User Input Command
    user_cmd = params.get('powerShellCommand')
    
    # 3. Pre-flight Check: Ensure the nginx user can access the cert
    if not os.path.exists(cert_path):
        raise ConnectorError(f"Certificate file not found at: {cert_path}")
    if not os.access(cert_path, os.R_OK):
        raise ConnectorError(f"Permission Denied: nginx user cannot read {cert_path}. Check 'chmod' and 'chown' on parent folders.")

    # 4. Construct the full script
    # This script explicitly sets the ModulePath to bypass environment isolation in Rocky Linux
    ps_script = f"""
    $ErrorActionPreference = 'Stop'
    
    # Explicitly add the global module path installed by root
    $CustomPath = "/usr/local/share/powershell/Modules"
    if ($env:PSModulePath -notlike "*$CustomPath*") {{
        $env:PSModulePath = "$CustomPath" + ":" + $env:PSModulePath
    }}

    # Import the module - ensure it's visible to nginx
    Import-Module ExchangeOnlineManagement -ErrorAction Stop
    
    try {{
        # Load the OpenSSL PEM directly
        $cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::CreateFromPemFile("{cert_path}")
        
        Connect-ExchangeOnline -AppId "{app_id}" `
                               -Certificate $cert `
                               -Organization "{org}" -ErrorAction Stop
        
        # Execute the user command
        $result = {user_cmd}
        
        if ($null -ne $result) {{
            # Depth 5 ensures nested objects are captured; Compress removes whitespace
            $result | ConvertTo-Json -Depth 5 -Compress
        }}
    }}
    finally {{
        Disconnect-ExchangeOnline -Confirm:$false
    }}
    """

    try:
        # 5. Execute via the Linux pwsh binary
        process = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            check=True
        )
        
        raw_output = process.stdout.strip()
        
        if raw_output:
            # 6. Parse logic: Strip PowerShell banners/disclaimers and find the JSON block
            # This regex looks for the first '{' and the last '}' to extract the valid JSON object
            json_match = re.search(r'(\{.*\})', raw_output, re.DOTALL)
            
            if json_match:
                clean_json_string = json_match.group(1)
                try:
                    return json.loads(clean_json_string)
                except json.JSONDecodeError as je:
                    logger.error(f"Failed to decode extracted JSON: {str(je)}")
                    return {"output": raw_output}
            else:
                # If no JSON braces found, return the raw string as 'output'
                return {"output": raw_output}
        
        return {"status": "Success", "message": "Command executed, but returned no data."}

    except subprocess.CalledProcessError as e:
        # Capture PowerShell errors cleanly
        error_msg = e.stderr.strip() if e.stderr else e.stdout.strip()
        logger.error(f"PowerShell Error: {error_msg}")
        raise ConnectorError(f"EXO PowerShell Error: {error_msg}")
    except Exception as e:
        logger.error(f"Unexpected Error: {str(e)}")
        raise ConnectorError(f"Internal Connector Error: {str(e)}")
import asyncio
import json
import time
import requests
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from aptos_sdk.account import Account
from aptos_sdk.async_client import RestClient
from aptos_sdk.transactions import EntryFunction, TransactionArgument, TransactionPayload
from aptos_sdk.bcs import Serializer

NODE_URL = "http://127.0.0.1:8080/v1"  # localnet
FAUCET_URL = "http://127.0.0.1:8081/mint"
KEYS_DIR = "keys"
KEY_FILE = "account1_private_key.txt"
DEFAULT_FUND_AMOUNT = 100_000_000

def save_private_key(account: Account, filepath: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        private_key_hex = account.private_key.hex()
        with open(filepath, "w") as f:
            f.write(private_key_hex)
        print(f"Saved private key to: {filepath}")
        print(f"Private key length: {len(private_key_hex)} characters")
    except Exception as e:
        print(f"Error saving private key: {e}")
        raise

def load_private_key(filepath: str) -> Account:
    try:
        with open(filepath, "r") as f:
            private_key_hex = f.read().strip()
        
        # Remove any potential prefixes or whitespace
        private_key_hex = private_key_hex.replace("0x", "").strip()
        
        # Validate hex string
        if not all(c in '0123456789abcdefABCDEF' for c in private_key_hex):
            raise ValueError("Invalid hex characters in private key")
        
        # Ensure correct length (64 characters for 32 bytes)
        if len(private_key_hex) != 64:
            raise ValueError(f"Invalid private key length: {len(private_key_hex)}, expected 64")
        
        private_key_bytes = bytes.fromhex(private_key_hex)
        account = Account.load_key(private_key_bytes)
        print(f"Loaded account from {filepath} with address: {account.address()}")
        return account
        
    except FileNotFoundError:
        print(f"Private key file not found: {filepath}")
        raise
    except ValueError as e:
        print(f"Error with private key format: {e}")
        print(f"Corrupted key file detected. Removing {filepath} and creating new account.")
        try:
            os.remove(filepath)
        except:
            pass
        raise
    except Exception as e:
        print(f"Unexpected error loading private key: {e}")
        print(f"Removing corrupted key file: {filepath}")
        try:
            os.remove(filepath)
        except:
            pass
        raise

async def fund_account(address: str, amount: int = DEFAULT_FUND_AMOUNT):
    params = {"address": address, "amount": amount}
    response = requests.post(FAUCET_URL, params=params)
    if response.status_code == 200:
        print(f"Funded account {address} with {amount} coins.")
    else:
        print(f"Failed to fund account {address}: {response.text}")
    time.sleep(1)

def save_upload_log(base_directory: str, upload_records: list, account_address: str):
    """Save upload log with transaction hashes and file information"""
    log_data = {
        "upload_session": {
            "timestamp": datetime.now().isoformat(),
            "account_address": account_address,
            "total_files": len(upload_records),
            "successful_uploads": len([r for r in upload_records if r["success"]]),
            "failed_uploads": len([r for r in upload_records if not r["success"]])
        },
        "files": upload_records
    }
    
    # Save to the main directory
    log_filename = f"upload_log_{int(time.time())}.json"
    log_path = Path(base_directory) / log_filename
    
    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        print(f"Upload log saved to: {log_path}")
        return str(log_path)
    except Exception as e:
        print(f"Error saving upload log: {e}")
        return None

def load_upload_log(log_path: str):
    """Load upload log from file"""
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading upload log: {e}")
        return None
def get_or_create_account() -> Account:
    filepath = os.path.join(KEYS_DIR, KEY_FILE)
    
    if os.path.exists(filepath):
        try:
            return load_private_key(filepath)
        except Exception as e:
            print(f"Failed to load existing account: {e}")
            print("Creating new account...")
    
    # Create new account if file doesn't exist or is corrupted
    account = Account.generate()
    save_private_key(account, filepath)
    print(f"Created new account with address {account.address()}")
    return account

def find_json_files(base_directory: str):
    """Find all JSON files in subdirectories of the given base directory"""
    json_files = []
    base_path = Path(base_directory)
    
    if not base_path.exists():
        print(f"Directory {base_directory} does not exist!")
        return json_files
    
    # Get all subdirectories
    for subdir in base_path.iterdir():
        if subdir.is_dir():
            print(f"Scanning directory: {subdir}")
            # Find all JSON files in this subdirectory
            for json_file in subdir.glob("*.json"):
                json_files.append(json_file)
                print(f"Found JSON file: {json_file}")
    
    return json_files

def load_json_file(filepath: Path):
    """Load and validate JSON file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file {filepath}: {e}")
        return None
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return None

async def store_json(client, account, json_string, module_address, filename=""):
    """Store JSON data on chain"""
    try:
        entry_function = EntryFunction.natural(
            f"{module_address}::json_storage",
            "store_json",
            [],
            [TransactionArgument(json_string, Serializer.str)]
        )
        signed_tx = await client.create_bcs_signed_transaction(account, TransactionPayload(entry_function))
        tx_hash = await client.submit_bcs_transaction(signed_tx)
        print(f"Transaction submitted for {filename}: {tx_hash}")
        await client.wait_for_transaction(tx_hash)
        print(f"JSON from {filename} stored on chain successfully.")
        return tx_hash
    except Exception as e:
        print(f"Error storing JSON from {filename}: {e}")
        return None

async def get_all_account_resources(client, account_address, module_address):
    """Get all resources for the account to verify uploads"""
    try:
        resources = await client.account_resources(account_address)
        json_resources = []
        
        for resource in resources:
            if resource['type'] == f"{module_address}::json_storage::JSONStorage":
                try:
                    json_data = json.loads(resource['data']['data'])
                    json_resources.append({
                        'type': resource['type'],
                        'data': json_data
                    })
                except json.JSONDecodeError:
                    json_resources.append({
                        'type': resource['type'],
                        'data': resource['data']['data'],
                        'note': 'Raw string data (not valid JSON)'
                    })
        
        return json_resources
    except Exception as e:
        print(f"Error retrieving account resources: {e}")
        return []

async def verify_uploads_on_chain(client, account_address, module_address, upload_records):
    """Verify that uploads are accessible on chain and print summary"""
    print("\n" + "="*80)
    print("BLOCKCHAIN VERIFICATION - RETRIEVING ALL UPLOADED RESOURCES")
    print("="*80)
    
    try:
        # Get transaction details for each upload
        for i, record in enumerate(upload_records):
            if not record["success"]:
                continue
                
            print(f"\n--- File {i+1}: {record['filename']} ---")
            print(f"Transaction Hash: {record['transaction_hash']}")
            
            try:
                # Get transaction details
                tx_info = await client.transaction_by_hash(record['transaction_hash'])
                print(f"Transaction Status: {tx_info.get('success', 'Unknown')}")
                print(f"Gas Used: {tx_info.get('gas_used', 'Unknown')}")
            except Exception as e:
                print(f"Could not retrieve transaction details: {e}")
        
        # Get current state of all resources
        print(f"\n--- CURRENT BLOCKCHAIN STATE FOR ACCOUNT {account_address} ---")
        resources = await get_all_account_resources(client, account_address, module_address)
        
        if resources:
            for i, resource in enumerate(resources):
                print(f"\nResource {i+1}:")
                print(f"Type: {resource['type']}")
                if isinstance(resource['data'], dict):
                    # Pretty print JSON data
                    print("Data:")
                    print(json.dumps(resource['data'], indent=2))
                else:
                    print(f"Data: {resource['data']}")
                    if 'note' in resource:
                        print(f"Note: {resource['note']}")
        else:
            print("No JSON storage resources found on chain!")
            
    except Exception as e:
        print(f"Error during verification: {e}")

async def get_transaction_by_hash(client, tx_hash):
    """Get transaction details by hash"""
    try:
        return await client.transaction_by_hash(tx_hash)
    except Exception as e:
        print(f"Error getting transaction {tx_hash}: {e}")
        return None

async def publish_module(account):
    """Publish the Move module to the blockchain"""
    temp_key_path = "temp_private_key.txt"
    try:
        with open(temp_key_path, "w") as f:
            f.write(account.private_key.hex())
        print(f"Saved private key for publishing to {temp_key_path}")

        # Compile Move package
        compile_cmd = [
            "aptos", "move", "compile",
            "--package-dir", ".",
            "--named-addresses", f"my_addr={account.address()}"
        ]
        compile_result = subprocess.run(compile_cmd, capture_output=True, text=True)
        print(f"Compile stdout:\n{compile_result.stdout}")
        if compile_result.stderr:
            print(f"Compile stderr:\n{compile_result.stderr}")
        if compile_result.returncode != 0:
            print("Compilation failed, aborting.")
            return False

        # Publish Move package
        publish_cmd = [
            "aptos", "move", "publish",
            "--assume-yes",
            "--private-key-file", temp_key_path,
            "--url", NODE_URL,
            "--package-dir", ".",
            "--named-addresses", f"my_addr={account.address()}"
        ]
        publish_result = subprocess.run(publish_cmd, capture_output=True, text=True)
        print(f"Publish stdout:\n{publish_result.stdout}")
        if publish_result.stderr:
            print(f"Publish stderr:\n{publish_result.stderr}")

        if publish_result.returncode != 0 or "Error" in publish_result.stdout:
            print("Module publication failed.")
            return False

        print("Module published successfully.")
        return True
    finally:
        if os.path.exists(temp_key_path):
            os.remove(temp_key_path)
            print(f"Removed temporary private key file {temp_key_path}")

async def upload_json_files(directory_path: str):
    """Main function to upload all JSON files from subdirectories"""
    client = RestClient(NODE_URL)
    account = get_or_create_account()
    
    # Fund account (safe to call multiple times)
    await fund_account(str(account.address()))

    # Publish module
    if not await publish_module(account):
        print("Exiting due to failure in publishing Move module.")
        return

    module_address = str(account.address())

    # Wait a bit for module to be available
    print("Waiting for module to be available on chain...")
    time.sleep(5)

    # Find all JSON files in subdirectories
    json_files = find_json_files(directory_path)
    
    if not json_files:
        print(f"No JSON files found in subdirectories of {directory_path}")
        await client.close()
        return

    print(f"Found {len(json_files)} JSON files to upload")
    
    # Process each JSON file and track results
    upload_records = []
    successful_uploads = 0
    failed_uploads = 0
    
    for json_file in json_files:
        print(f"\n--- Processing {json_file} ---")
        
        # Create record for this file
        file_record = {
            "filename": json_file.name,
            "filepath": str(json_file),
            "directory": json_file.parent.name,
            "upload_timestamp": int(time.time()),
            "success": False,
            "transaction_hash": None,
            "error_message": None,
            "file_size_bytes": None
        }
        
        try:
            # Get file size
            file_record["file_size_bytes"] = json_file.stat().st_size
        except:
            pass
        
        # Load JSON data
        json_data = load_json_file(json_file)
        if json_data is None:
            print(f"Skipping {json_file} due to loading error")
            file_record["error_message"] = "Failed to load/parse JSON file"
            upload_records.append(file_record)
            failed_uploads += 1
            continue
        
        # Add metadata about the file
        json_data['_metadata'] = {
            'original_file': str(json_file),
            'filename': json_file.name,
            'directory': json_file.parent.name,
            'upload_timestamp': int(time.time()),
            'uploader_address': module_address
        }
        
        json_string = json.dumps(json_data)
        
        # Store JSON on-chain
        tx_hash = await store_json(client, account, json_string, module_address, json_file.name)
        
        if tx_hash:
            file_record["success"] = True
            file_record["transaction_hash"] = tx_hash
            successful_uploads += 1
            print(f"Successfully uploaded {json_file.name} - TX: {tx_hash}")
        else:
            file_record["error_message"] = "Failed to store on blockchain"
            failed_uploads += 1
            print(f"Failed to upload {json_file.name}")
        
        upload_records.append(file_record)
        
        # Add small delay between uploads
        time.sleep(2)

    print(f"\n--- Upload Summary ---")
    print(f"Total files processed: {len(json_files)}")
    print(f"Successful uploads: {successful_uploads}")
    print(f"Failed uploads: {failed_uploads}")
    
    # Save upload log to main directory
    log_path = save_upload_log(directory_path, upload_records, module_address)
    if log_path:
        print(f"Detailed upload log saved to: {log_path}")
    
    # Verify uploads on blockchain and print all resources
    if successful_uploads > 0:
        await verify_uploads_on_chain(client, account.address(), module_address, upload_records)
        
        # Print hash summary for quick reference
        print(f"\n--- TRANSACTION HASH SUMMARY ---")
        for record in upload_records:
            if record["success"]:
                print(f"{record['filename']} -> {record['transaction_hash']}")
    
    await client.close()
    
    return upload_records

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Upload files: python script.py <directory_path>")
        print("  View log: python script.py --view-log <log_file_path>")
        print("\nExamples:")
        print("  python script.py /path/to/your/data/directory")
        print("  python script.py --view-log /path/to/upload_log_1234567890.json")
        sys.exit(1)
    
    if sys.argv[1] == "--view-log" and len(sys.argv) == 3:
        # View existing log file
        log_path = sys.argv[2]
        log_data = load_upload_log(log_path)
        if log_data:
            print("="*80)
            print("UPLOAD LOG VIEWER")
            print("="*80)
            print(f"Session Timestamp: {log_data['upload_session']['timestamp']}")
            print(f"Account Address: {log_data['upload_session']['account_address']}")
            print(f"Total Files: {log_data['upload_session']['total_files']}")
            print(f"Successful: {log_data['upload_session']['successful_uploads']}")
            print(f"Failed: {log_data['upload_session']['failed_uploads']}")
            
            print(f"\n--- FILE DETAILS ---")
            for file_info in log_data['files']:
                print(f"\nFile: {file_info['filename']}")
                print(f"  Directory: {file_info['directory']}")
                print(f"  Success: {file_info['success']}")
                if file_info['success']:
                    print(f"  Transaction Hash: {file_info['transaction_hash']}")
                else:
                    print(f"  Error: {file_info.get('error_message', 'Unknown error')}")
        return
    
    directory_path = sys.argv[1]
    print(f"Starting JSON file upload from directory: {directory_path}")
    
    asyncio.run(upload_json_files(directory_path))

if __name__ == "__main__":
    main()
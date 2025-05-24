import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from aptos_sdk.account import Account
from aptos_sdk.async_client import RestClient

NODE_URL = "http://127.0.0.1:8080/v1"  # localnet
KEYS_DIR = "keys"
KEY_FILE = "account1_private_key.txt"
DOWNLOADS_DIR = "downloads"

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
        
    except Exception as e:
        print(f"Error loading private key: {e}")
        raise

def load_upload_log(log_path: str):
    """Load upload log from file"""
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading upload log: {e}")
        return None

def save_fetched_data(data, filename, download_dir, transaction_hash=None):
    """Save fetched data to local file"""
    os.makedirs(download_dir, exist_ok=True)
    
    # Create filename with timestamp
    timestamp = int(time.time())
    if transaction_hash:
        safe_hash = transaction_hash[:8]  # First 8 chars of hash
        output_filename = f"{filename}_{safe_hash}_{timestamp}.json"
    else:
        output_filename = f"{filename}_{timestamp}.json"
    
    output_path = os.path.join(download_dir, output_filename)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved fetched data to: {output_path}")
        return output_path
    except Exception as e:
        print(f"Error saving fetched data: {e}")
        return None

async def extract_json_data_from_transaction(client, tx_hash):
    """Extract the actual JSON data payload from a transaction"""
    try:
        print(f"Extracting data from transaction: {tx_hash}")
        tx_info = await client.transaction_by_hash(tx_hash)
        
        # Check if transaction was successful
        if not tx_info.get('success', False):
            print(f"Transaction {tx_hash} was not successful")
            return None
        
        # Look for the JSON data in the transaction payload
        # The data should be in the function arguments or events
        
        # Method 1: Check transaction payload/changes
        if 'payload' in tx_info:
            payload = tx_info['payload']
            if 'arguments' in payload:
                # The JSON data should be in the arguments
                for arg in payload['arguments']:
                    try:
                        # Try to parse as JSON
                        if isinstance(arg, str) and (arg.startswith('{') or arg.startswith('[')):
                            json_data = json.loads(arg)
                            print(f"Found JSON data in transaction arguments")
                            return json_data
                    except json.JSONDecodeError:
                        continue
        
        # Method 2: Check transaction events
        if 'events' in tx_info:
            for event in tx_info['events']:
                if 'data' in event:
                    event_data = event['data']
                    # Look for JSON string in event data
                    for key, value in event_data.items():
                        if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                            try:
                                json_data = json.loads(value)
                                print(f"Found JSON data in event: {event['type']}")
                                return json_data
                            except json.JSONDecodeError:
                                continue
        
        # Method 3: Check transaction changes (state changes)
        if 'changes' in tx_info:
            for change in tx_info['changes']:
                if change.get('type') == 'write_resource':
                    resource_data = change.get('data', {})
                    # Look for JSON data in resource changes
                    if 'data' in resource_data:
                        data_field = resource_data['data']
                        if isinstance(data_field, dict) and 'data' in data_field:
                            json_string = data_field['data']
                            if isinstance(json_string, str):
                                try:
                                    json_data = json.loads(json_string)
                                    print(f"Found JSON data in resource changes")
                                    return json_data
                                except json.JSONDecodeError:
                                    continue
        
        print(f"No JSON data found in transaction {tx_hash}")
        return None
        
    except Exception as e:
        print(f"Error extracting data from transaction {tx_hash}: {e}")
        return None

async def get_transaction_details(client, tx_hash):
    """Get detailed transaction information"""
    try:
        tx_info = await client.transaction_by_hash(tx_hash)
        return {
            'hash': tx_hash,
            'success': tx_info.get('success', False),
            'gas_used': tx_info.get('gas_used', 0),
            'timestamp': tx_info.get('timestamp', ''),
            'sender': tx_info.get('sender', ''),
            'type': tx_info.get('type', ''),
            'version': tx_info.get('version', '')
        }
    except Exception as e:
        print(f"Error getting transaction details for {tx_hash}: {e}")
        return None

async def get_account_resource_data(client, account_address, module_address):
    """Get JSON data stored in account resources"""
    try:
        resources = await client.account_resources(account_address)
        for resource in resources:
            if resource['type'] == f"{module_address}::json_storage::JSONStorage":
                json_string = resource['data']['data']
                return json.loads(json_string)
        return None
    except Exception as e:
        print(f"Error retrieving account resource data: {e}")
        return None

async def fetch_all_json_data_from_log(log_path: str, download_dir: str = None):
    """Fetch all individual JSON data from transactions referenced in the upload log"""
    
    # Load the upload log
    log_data = load_upload_log(log_path)
    if not log_data:
        print("Failed to load upload log")
        return
    
    # Setup download directory
    if not download_dir:
        download_dir = os.path.join(DOWNLOADS_DIR, f"json_data_fetch_{int(time.time())}")
    
    print(f"Download directory: {download_dir}")
    
    # Initialize client
    client = RestClient(NODE_URL)
    
    try:
        print("="*80)
        print("FETCHING INDIVIDUAL JSON DATA FROM BLOCKCHAIN")
        print("="*80)
        print(f"Log File: {log_path}")
        print(f"Total Files in Log: {log_data['upload_session']['total_files']}")
        
        # Create summary data
        fetch_summary = {
            "fetch_session": {
                "timestamp": datetime.now().isoformat(),
                "log_file": log_path,
                "download_directory": download_dir,
                "total_files_attempted": 0,
                "successful_extractions": 0,
                "failed_extractions": 0
            },
            "extracted_files": [],
            "failed_files": []
        }
        
        # Process each successful upload
        successful_files = [f for f in log_data['files'] if f['success']]
        print(f"\nProcessing {len(successful_files)} successful transactions...")
        
        for file_info in successful_files:
            tx_hash = file_info['transaction_hash']
            original_filename = file_info['filename']
            directory = file_info.get('directory', 'unknown')
            
            print(f"\n--- Processing {original_filename} from {directory} ---")
            fetch_summary["fetch_session"]["total_files_attempted"] += 1
            
            # Extract JSON data from transaction
            json_data = await extract_json_data_from_transaction(client, tx_hash)
            
            if json_data:
                # Save the extracted JSON data with original filename structure
                clean_filename = original_filename.replace('.json', '')
                output_filename = f"{directory}_{clean_filename}_extracted"
                
                output_path = save_fetched_data(json_data, output_filename, download_dir, tx_hash)
                
                fetch_summary["extracted_files"].append({
                    "original_filename": original_filename,
                    "directory": directory,
                    "transaction_hash": tx_hash,
                    "extracted_data": json_data,
                    "output_file": output_path,
                    "extraction_timestamp": datetime.now().isoformat()
                })
                
                fetch_summary["fetch_session"]["successful_extractions"] += 1
                print(f"✓ Successfully extracted data from {original_filename}")
                
                # Print a preview of the extracted data
                print(f"Preview: {json.dumps(json_data, indent=2)[:200]}...")
                
            else:
                fetch_summary["failed_files"].append({
                    "original_filename": original_filename,
                    "directory": directory,
                    "transaction_hash": tx_hash,
                    "error": "Could not extract JSON data from transaction"
                })
                
                fetch_summary["fetch_session"]["failed_extractions"] += 1
                print(f"✗ Failed to extract data from {original_filename}")
            
            # Small delay between requests
            await asyncio.sleep(0.5)
        
        # Save comprehensive summary
        summary_path = save_fetched_data(fetch_summary, "extraction_summary", download_dir)
        
        print(f"\n" + "="*80)
        print("EXTRACTION COMPLETE")
        print("="*80)
        print(f"Downloads saved to: {download_dir}")
        print(f"Summary file: {summary_path}")
        print(f"Successful extractions: {fetch_summary['fetch_session']['successful_extractions']}")
        print(f"Failed extractions: {fetch_summary['fetch_session']['failed_extractions']}")
        print(f"Success rate: {fetch_summary['fetch_session']['successful_extractions']}/{fetch_summary['fetch_session']['total_files_attempted']}")
        
        # Also create a combined file with all extracted data
        if fetch_summary["extracted_files"]:
            combined_data = {
                "extraction_info": {
                    "timestamp": datetime.now().isoformat(),
                    "total_files": len(fetch_summary["extracted_files"]),
                    "source_log": log_path
                },
                "files": {}
            }
            
            for file_data in fetch_summary["extracted_files"]:
                key = f"{file_data['directory']}/{file_data['original_filename']}"
                combined_data["files"][key] = {
                    "transaction_hash": file_data["transaction_hash"],
                    "data": file_data["extracted_data"]
                }
            
            combined_path = save_fetched_data(combined_data, "all_extracted_data_combined", download_dir)
            print(f"Combined data file: {combined_path}")
        
        return fetch_summary
        
    finally:
        await client.close()

async def fetch_single_json_from_transaction(tx_hash: str, download_dir: str = None):
    """Fetch JSON data from a specific transaction hash"""
    
    if not download_dir:
        download_dir = os.path.join(DOWNLOADS_DIR, f"single_json_fetch_{int(time.time())}")
    
    client = RestClient(NODE_URL)
    
    try:
        print(f"Extracting JSON data from transaction: {tx_hash}")
        json_data = await extract_json_data_from_transaction(client, tx_hash)
        
        if json_data:
            output_path = save_fetched_data(json_data, "extracted_json_data", download_dir, tx_hash)
            print(f"JSON data saved to: {output_path}")
            print(f"Extracted data: {json.dumps(json_data, indent=2)}")
            return json_data
        else:
            print("Failed to extract JSON data from transaction")
            return None
            
    finally:
        await client.close()

async def fetch_current_account_data(client, account_address, module_address):
    """Fetch current data stored in account resources"""
    print(f"\n--- Fetching Current Account Data: {account_address} ---")
    
    data = await get_account_resource_data(client, account_address, module_address)
    if data:
        print("Successfully retrieved current account data")
        return data
    else:
        print("No data found in account resources")
        return None

async def fetch_account_current_data(account_addr: str = None, download_dir: str = None):
    """Fetch current data from account (requires account address)"""
    
    if not account_addr:
        # Try to get from saved account
        try:
            filepath = os.path.join(KEYS_DIR, KEY_FILE)
            account = load_private_key(filepath)
            account_addr = str(account.address())
        except:
            print("No account address provided and couldn't load from saved account")
            return None
    
    if not download_dir:
        download_dir = os.path.join(DOWNLOADS_DIR, f"account_fetch_{int(time.time())}")
    
    client = RestClient(NODE_URL)
    
    try:
        print(f"Fetching current data for account: {account_addr}")
        data = await fetch_current_account_data(client, account_addr, account_addr)
        
        if data:
            output_path = save_fetched_data(data, "account_data", download_dir)
            print(f"Account data saved to: {output_path}")
            return data
        else:
            print("No data found for account")
            return None
            
    finally:
        await client.close()

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Fetch individual JSON data from log file:")
        print("    python fetcher.py --extract-log <log_file_path> [download_dir]")
        print("  Fetch JSON data from specific transaction:")
        print("    python fetcher.py --extract-tx <transaction_hash> [download_dir]")
        print("  Fetch current account data:")
        print("    python fetcher.py --account [account_address] [download_dir]")
        print("\nExamples:")
        print("  python fetcher.py --extract-log upload_log_1234567890.json")
        print("  python fetcher.py --extract-tx 0x2384de0a51f82517d400bbd158391eeed50e69479918d70a3709d75dc7f9a737")
        print("  python fetcher.py --account 0x123abc...")
        print("  python fetcher.py --account")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "--extract-log" and len(sys.argv) >= 3:
        log_path = sys.argv[2]
        download_dir = sys.argv[3] if len(sys.argv) > 3 else None
        asyncio.run(fetch_all_json_data_from_log(log_path, download_dir))
        
    elif command == "--extract-tx" and len(sys.argv) >= 3:
        tx_hash = sys.argv[2]
        download_dir = sys.argv[3] if len(sys.argv) > 3 else None
        asyncio.run(fetch_single_json_from_transaction(tx_hash, download_dir))
        
    elif command == "--account":
        account_addr = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('downloads') else None
        download_dir = sys.argv[3] if len(sys.argv) > 3 else (sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].startswith('downloads') else None)
        asyncio.run(fetch_account_current_data(account_addr, download_dir))
        
    else:
        print("Invalid command. Use --help for usage information")
        sys.exit(1)

if __name__ == "__main__":
    main()
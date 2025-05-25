import os
import subprocess
import tempfile
import shutil
import requests
import logging
from pathlib import Path
from aptos_sdk.account import Account
from aptos_sdk.account_address import AccountAddress
from aptos_sdk.client import RestClient, FaucetClient
from aptos_sdk.transactions import EntryFunction, TransactionPayload, TransactionArgument
from aptos_sdk.bcs import Serializer
from aptos_sdk import ed25519
from dotenv import load_dotenv
import json

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Aptos configuration
NODE_URL = os.getenv("APTOS_NODE_URL", "http://localhost:8080/v1")  # Add /v1 to the URL
FAUCET_URL = os.getenv("APTOS_FAUCET_URL", "http://localhost:8081")
MODULE_ADDRESS = os.getenv("MODULE_ADDRESS", "my_addr")

def get_aptos_client():
    """Get an Aptos REST client."""
    # Add custom debugging code before returning the client
    try:
        logger.info(f"Connecting to Aptos node at: {NODE_URL}")
        
        # Make a direct request to test the connection
        response = requests.get(f"{NODE_URL}")
        logger.info(f"Status code from Aptos node: {response.status_code}")
        logger.info(f"Response headers: {response.headers}")
        
        # Log the raw response content
        try:
            logger.info(f"Raw response content: {response.text[:1000]}")  # Limit to first 1000 chars
        except Exception as e:
            logger.error(f"Error logging response content: {str(e)}")

        # Try to parse it as JSON to see if it's valid
        try:
            json_data = response.json()
            logger.info(f"Parsed JSON response: {json_data}")
        except Exception as e:
            logger.error(f"Error parsing JSON response: {str(e)}")
        
        return RestClient(NODE_URL)
    except Exception as e:
        logger.error(f"Error creating RestClient: {str(e)}")
        raise

def create_aptos_account():
    """Create a new Aptos account and fund it with 100 million octas."""
    try:
        logger.info("Creating new Aptos account")
        # Generate a random account
        account = Account.generate()
        logger.info(f"Generated account with address: {account.address()}")
        
        try:
            client = get_aptos_client()
            logger.info("Successfully created Aptos client")
        except Exception as e:
            logger.error(f"Error creating Aptos client: {str(e)}")
            raise
    
        try:
            # Fund the account with 100 million octas
            logger.info(f"Attempting to fund account via faucet at {FAUCET_URL}")
            faucet_client = FaucetClient(FAUCET_URL, client)
            faucet_client.fund_account(account.address(), 100000000)
            logger.info(f"Funded account {account.address()} with 100 million octas")
        except Exception as e:
            logger.warning(f"Could not fund account via faucet: {str(e)}")
            logger.warning("Continuing without funding. Account may not be able to submit transactions.")
            raise
        
        return {
            "address": str(account.address()),
            "private_key": account.private_key.hex(),
            "public_key": str(account.public_key())  # Convert to string instead of calling hex()
        }
    except Exception as e:
        logger.error(f"Error in create_aptos_account: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

def check_module_exists(account_address):
    """Check if the json_storage module already exists on chain for the given account."""
    try:
        # Initialize the Aptos client
        client = get_aptos_client()
        
        # Format address
        if account_address.startswith("0x"):
            account_address_clean = account_address[2:]
        else:
            account_address_clean = account_address
            
        logger.info(f"Checking if json_storage module exists for account: 0x{account_address_clean}")
        
        # Make API request to get account modules
        try:
            response = requests.get(f"{NODE_URL}/accounts/0x{account_address_clean}/modules")
            
            if response.status_code == 200:
                modules = response.json()
                
                # Check if json_storage module exists
                for module in modules:
                    if module.get('abi', {}).get('name') == 'json_storage':
                        logger.info(f"json_storage module already exists for account: 0x{account_address_clean}")
                        return True
                        
                logger.info(f"json_storage module does not exist for account: 0x{account_address_clean}")
                return False
            else:
                logger.warning(f"Failed to get modules for account: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error checking modules: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Error in check_module_exists: {str(e)}")
        return False

def publish_module(admin_private_key, admin_address=None):
    """Compile and publish the json_storage module using the admin's private key."""
    try:
        # Declare MODULE_ADDRESS as global at the beginning of the function
        global MODULE_ADDRESS
        
        # Initialize the Aptos client
        client = get_aptos_client()
        
        if not admin_private_key:
            raise ValueError("Admin private key is not available")
        
        # Remove '0x' prefix if present
        if admin_private_key.startswith("0x"):
            admin_private_key = admin_private_key[2:]
            
        # Format address properly
        if admin_address:
            if admin_address.startswith("0x"):
                admin_address_clean = admin_address[2:]
            else:
                admin_address_clean = admin_address
        else:
            logger.error("Admin address is required for module publishing")
            raise ValueError("Admin address is required")
            
        # Check if module already exists on chain
        if check_module_exists(f"0x{admin_address_clean}"):
            logger.info(f"json_storage module already exists for account 0x{admin_address_clean}. Skipping publishing.")
            
            # Update the MODULE_ADDRESS global variable to use the admin's address
            MODULE_ADDRESS = f"0x{admin_address_clean}"
            
            return True
        
        # Get the current working directory
        current_dir = os.getcwd()
        
        # Check if the Move.toml file exists
        move_toml_path = os.path.join(current_dir, "Move.toml")
        json_storage_path = os.path.join(current_dir, "sources", "json_storage.move")
        
        if not os.path.exists(move_toml_path):
            raise FileNotFoundError(f"Move.toml not found at {move_toml_path}")
        
        if not os.path.exists(json_storage_path):
            raise FileNotFoundError(f"json_storage.move not found at {json_storage_path}")
        
        logger.info(f"Found Move files: {move_toml_path} and {json_storage_path}")
        
        # Create a temporary directory for the module
        with tempfile.TemporaryDirectory() as temp_dir:
            # Copy the Move.toml and sources directory to the temp directory
            shutil.copy(move_toml_path, os.path.join(temp_dir, "Move.toml"))
            os.makedirs(os.path.join(temp_dir, "sources"), exist_ok=True)
            shutil.copy(json_storage_path, os.path.join(temp_dir, "sources", "json_storage.move"))
            
            # Update the module address in the json_storage.move file
            try:
                with open(os.path.join(temp_dir, "sources", "json_storage.move"), 'r') as file:
                    content = file.read()
                
                # Replace my_addr with the actual module owner address
                updated_content = content.replace("my_addr", f"0x{admin_address_clean}")
                
                with open(os.path.join(temp_dir, "sources", "json_storage.move"), 'w') as file:
                    file.write(updated_content)
                
                logger.info(f"Updated module address to 0x{admin_address_clean}")
            except Exception as e:
                logger.error(f"Error updating module address: {str(e)}")
                raise
            
            # Compile the module
            logger.info(f"Compiling module with address 0x{admin_address_clean}")
            compile_cmd = [
                "aptos", "move", "compile",
                "--package-dir", temp_dir,
                "--named-addresses", f"my_addr=0x{admin_address_clean}"
            ]
            
            try:
                compile_result = subprocess.run(compile_cmd, check=True, capture_output=True, text=True)
                logger.info(f"Compilation output: {compile_result.stdout}")
                logger.info("Module compiled successfully")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to compile module: {str(e)}")
                logger.error(f"Command output: {e.stdout if hasattr(e, 'stdout') else 'No output'}")
                logger.error(f"Command error: {e.stderr if hasattr(e, 'stderr') else 'No error'}")
                raise
            
            # Publish the module
            logger.info(f"Publishing module with address 0x{admin_address_clean}")
            publish_cmd = [
                "aptos", "move", "publish",
                "--assume-yes",
                "--private-key", admin_private_key,
                "--url", NODE_URL,
                "--package-dir", temp_dir,
                "--named-addresses", f"my_addr=0x{admin_address_clean}"
            ]
            
            try:
                publish_result = subprocess.run(publish_cmd, check=True, capture_output=True, text=True)
                logger.info(f"Publish output: {publish_result.stdout}")
                logger.info(f"Module published successfully by account: 0x{admin_address_clean}")
                
                # Update the MODULE_ADDRESS global variable to use the admin's address
                MODULE_ADDRESS = f"0x{admin_address_clean}"
                
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to publish module: {str(e)}")
                logger.error(f"Command output: {e.stdout if hasattr(e, 'stdout') else 'No output'}")
                logger.error(f"Command error: {e.stderr if hasattr(e, 'stderr') else 'No error'}")
                raise
    except Exception as e:
        logger.error(f"Error publishing module: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

def store_json_on_chain(account_address, private_key_hex, json_data):
    """Store JSON data on the Aptos blockchain."""
    try:
        # Initialize Aptos client and user account
        client = get_aptos_client()
        
        # Remove '0x' prefix if present
        if private_key_hex.startswith("0x"):
            private_key_hex = private_key_hex[2:]
            
        # Remove '0x' prefix from address if present
        if account_address.startswith("0x"):
            account_address_clean = account_address[2:]
        else:
            account_address_clean = account_address
        
        # Create account from private key and address
        try:
            # Create a proper PrivateKey object instead of using raw bytes
            private_key = ed25519.PrivateKey.from_hex(private_key_hex)
            # Need to convert string address to AccountAddress type
            addr_bytes = bytes.fromhex(account_address_clean)
            acct_address = AccountAddress(addr_bytes)
            user_account = Account(account_address=acct_address, private_key=private_key)
            
            logger.info(f"Created user account with address: {user_account.address()}")
        except Exception as e:
            logger.error(f"Error creating account from private key: {str(e)}")
            raise
            
        # Make sure the JSON data is a string
        if not isinstance(json_data, str):
            json_data = json.dumps(json_data)
            
        # Construct a transaction to call store_json function
        logger.info(f"Constructing transaction to store JSON data for account: {user_account.address()}")
        payload = TransactionPayload(
            EntryFunction.natural(
                f"{MODULE_ADDRESS}::json_storage",  # Module name in format "address::module_name"
                "store_json",                       # Function name
                [],                                # Type arguments (none for this function)
                [TransactionArgument(json_data, Serializer.str)]  # Properly serialize the string argument
            )
        )
        
        # Submit the transaction
        logger.info(f"Submitting transaction to store JSON data")
        
        # Create a signed transaction with BCS serialization
        signed_txn = client.create_bcs_signed_transaction(user_account, payload)
        
        # Submit the BCS transaction
        tx_hash = client.submit_bcs_transaction(signed_txn)
        
        logger.info(f"Transaction submitted with hash: {tx_hash}")
        
        # Wait for transaction to complete
        client.wait_for_transaction(tx_hash)
        logger.info(f"Transaction completed successfully")
        
        # Return success
        return {
            "success": True,
            "transaction_hash": tx_hash,
            "account_address": str(user_account.address())
        }
            
    except Exception as e:
        logger.error(f"Error storing JSON on chain: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }

def retrieve_json_from_chain(account_address):
    """Retrieve JSON data from the Aptos blockchain."""
    try:
        # Initialize Aptos client
        client = get_aptos_client()
        
        # Remove '0x' prefix from address if present
        if account_address.startswith("0x"):
            account_address_clean = account_address[2:]
        else:
            account_address_clean = account_address
            
        # Convert address string to AccountAddress
        addr_bytes = bytes.fromhex(account_address_clean)
        target_address = AccountAddress(addr_bytes)
        
        # Call the get_json function view function
        logger.info(f"Retrieving JSON data for account: {target_address}")
        
        result = client.account_resource(
            target_address,
            f"{MODULE_ADDRESS}::json_storage::JSONStorage"
        )
        
        if not result or 'data' not in result:
            return {
                "success": False,
                "error": "No JSON data found for this account"
            }
            
        # Extract the JSON data from the resource
        json_data = result['data']['data']
        
        # Parse the JSON string
        try:
            parsed_data = json.loads(json_data)
            return {
                "success": True,
                "json_data": parsed_data
            }
        except json.JSONDecodeError:
            # If it's not valid JSON, return it as a string
            return {
                "success": True,
                "json_data": json_data
            }
            
    except Exception as e:
        logger.error(f"Error retrieving JSON from chain: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        } 
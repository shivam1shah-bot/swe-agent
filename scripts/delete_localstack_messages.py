#!/usr/bin/env python3
"""
Utility script to delete messages from LocalStack SQS queues.

Usage:
    python scripts/delete_localstack_messages.py                    # Delete from default queue
    python scripts/delete_localstack_messages.py --queue QUEUE_NAME # Delete from specific queue
    python scripts/delete_localstack_messages.py --all              # Delete from all queues
"""

import argparse
import sys
import urllib.request
from typing import List, Dict, Any

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("Error: boto3 is required. Install with: pip install boto3")
    sys.exit(1)


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    NC = '\033[0m'  # No Color


class LocalStackMessageDeleter:
    """Utility class to manage LocalStack SQS message deletion."""
    
    def __init__(self):
        """Initialize the LocalStack SQS client."""
        print(f"{Colors.GREEN}🧹 LocalStack Queue Manager{Colors.NC}")
        
        # Check LocalStack health first
        if not self._check_localstack_health():
            sys.exit(1)
        
        # LocalStack SQS client
        self.sqs_client = boto3.client(
            'sqs',
            region_name='ap-south-1',
            endpoint_url='http://localhost:4566',
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )
        print(f"{Colors.GREEN}🔗 Connected to LocalStack SQS{Colors.NC}")
    
    def _check_localstack_health(self) -> bool:
        """Check if LocalStack is running and healthy."""
        try:
            response = urllib.request.urlopen('http://localhost:4566/_localstack/health', timeout=5)
            if response.status == 200:
                print(f"{Colors.GREEN}✅ LocalStack running{Colors.NC}")
                return True
        except Exception:
            pass
        
        print(f"{Colors.RED}❌ LocalStack not running{Colors.NC}")
        print(f"{Colors.YELLOW}💡 Start with: docker-compose up -d localstack{Colors.NC}")
        return False
    
    def test_connection(self) -> bool:
        """Test SQS connection to LocalStack."""
        try:
            self.sqs_client.list_queues()
            print(f"{Colors.GREEN}✅ SQS connection successful{Colors.NC}")
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ Failed to connect to SQS: {e}{Colors.NC}")
            return False
    
    def list_queues(self) -> List[Dict[str, Any]]:
        """List all SQS queues with message counts."""
        try:
            response = self.sqs_client.list_queues()
            queue_urls = response.get('QueueUrls', [])
            
            queues = []
            for queue_url in queue_urls:
                queue_name = queue_url.split('/')[-1]
                
                try:
                    attrs = self.sqs_client.get_queue_attributes(
                        QueueUrl=queue_url,
                        AttributeNames=['ApproximateNumberOfMessages']
                    )
                    message_count = int(attrs['Attributes'].get('ApproximateNumberOfMessages', 0))
                    
                    queues.append({
                        'name': queue_name,
                        'url': queue_url,
                        'message_count': message_count
                    })
                except Exception:
                    queues.append({
                        'name': queue_name,
                        'url': queue_url,
                        'message_count': 'unknown'
                    })
            
            return queues
            
        except Exception as e:
            print(f"{Colors.RED}❌ Failed to list queues: {e}{Colors.NC}")
            return []
    
    def print_queues(self, queues: List[Dict[str, Any]]) -> None:
        """Print queue information."""
        if not queues:
            print(f"{Colors.YELLOW}📭 No queues found in LocalStack{Colors.NC}")
            return
        
        print(f"\n📋 Found {len(queues)} queue(s):")
        for queue in queues:
            print(f"  • {queue['name']}: {queue['message_count']} messages")
    
    def purge_queue(self, queue_url: str, queue_name: str) -> bool:
        """Purge all messages from a queue."""
        try:
            print(f"🧹 Purging messages from queue: {queue_name}")
            self.sqs_client.purge_queue(QueueUrl=queue_url)
            print(f"{Colors.GREEN}✅ Successfully purged all messages from {queue_name}{Colors.NC}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'PurgeQueueInProgress':
                print(f"{Colors.YELLOW}⚠️  Queue {queue_name} is already being purged{Colors.NC}")
                return True
            else:
                print(f"{Colors.RED}❌ Failed to purge queue {queue_name}: {e}{Colors.NC}")
                return False
        except Exception as e:
            print(f"{Colors.RED}❌ Failed to purge queue {queue_name}: {e}{Colors.NC}")
            return False
    
    def delete_from_queue(self, queue_name: str) -> bool:
        """Delete all messages from a specific queue."""
        queues = self.list_queues()
        queue_info = next((q for q in queues if q['name'] == queue_name), None)
        
        if not queue_info:
            print(f"{Colors.RED}❌ Queue '{queue_name}' not found{Colors.NC}")
            available_queues = [q['name'] for q in queues]
            if available_queues:
                print(f"{Colors.YELLOW}💡 Available queues: {', '.join(available_queues)}{Colors.NC}")
            return False
        
        if queue_info['message_count'] == 0:
            print(f"{Colors.YELLOW}📭 Queue '{queue_name}' is already empty{Colors.NC}")
            return True
        
        return self.purge_queue(queue_info['url'], queue_name)
    
    def delete_from_all_queues(self) -> None:
        """Delete all messages from all queues."""
        queues = self.list_queues()
        
        if not queues:
            print(f"{Colors.YELLOW}📭 No queues found{Colors.NC}")
            return
        
        queues_with_messages = [q for q in queues if q['message_count'] != 0 and q['message_count'] != 'unknown']
        
        if not queues_with_messages:
            print(f"{Colors.YELLOW}📭 All queues are already empty{Colors.NC}")
            return
        
        print(f"\n🧹 Deleting messages from {len(queues_with_messages)} queue(s):")
        
        for queue in queues_with_messages:
            print(f"\n➡️  Processing: {queue['name']} ({queue['message_count']} messages)")
            self.purge_queue(queue['url'], queue['name'])


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Delete messages from LocalStack SQS queues",
        epilog="Examples:\n"
               "  python scripts/delete_localstack_messages.py\n"
               "  python scripts/delete_localstack_messages.py --queue dev-swe-agent-tasks\n"
               "  python scripts/delete_localstack_messages.py --all",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--queue', '-q',
        type=str,
        default='dev-swe-agent-tasks',
        help='Delete messages from specific queue (default: dev-swe-agent-tasks)'
    )
    
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Delete messages from all queues'
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize the deleter (includes health checks)
        deleter = LocalStackMessageDeleter()
        
        # Test SQS connection
        if not deleter.test_connection():
            sys.exit(1)
        
        if args.all:
            # Delete from all queues
            queues = deleter.list_queues()
            deleter.print_queues(queues)
            
            total_messages = sum(q['message_count'] for q in queues if isinstance(q['message_count'], int))
            if total_messages > 0:
                print(f"\n{Colors.YELLOW}⚠️  About to delete {total_messages} messages from {len(queues)} queue(s){Colors.NC}")
                response = input("❓ Continue? (y/N): ").strip().lower()
                
                if response not in ['y', 'yes']:
                    print(f"{Colors.RED}❌ Cancelled{Colors.NC}")
                    sys.exit(0)
                
                deleter.delete_from_all_queues()
            else:
                print(f"{Colors.YELLOW}📭 No messages to delete{Colors.NC}")
        else:
            # Delete from specific queue
            success = deleter.delete_from_queue(args.queue)
            sys.exit(0 if success else 1)
    
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}❌ Interrupted{Colors.NC}")
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.RED}❌ Error: {e}{Colors.NC}")
        sys.exit(1)


if __name__ == "__main__":
    main() 
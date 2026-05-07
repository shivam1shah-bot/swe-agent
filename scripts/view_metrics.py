#!/usr/bin/env python3
"""
View Code Review Metrics

This script displays the generated metrics data in a readable format.

Usage:
    python scripts/view_metrics.py --repo pg-router --date 2024-08-28
    python scripts/view_metrics.py --repo pg-router --date 2024-08-28 --format json
    python scripts/view_metrics.py --repo pg-router --date 2024-08-28 --raw
"""

import json
import argparse
from pathlib import Path
from typing import Dict, Any


def load_metrics_data(repo: str, date: str, raw: bool = False) -> Dict[str, Any]:
    """Load metrics data from file"""
    
    if raw:
        filepath = Path(f"uploads/metrics/raw/{date}/{repo}-raw.json")
    else:
        filepath = Path(f"uploads/metrics/extracted/{date}/{repo}-metrics.json")
    
    if not filepath.exists():
        raise FileNotFoundError(f"Metrics file not found: {filepath}")
    
    with open(filepath, 'r') as f:
        return json.load(f)


def display_summary(data: Dict[str, Any], raw: bool = False):
    """Display a formatted summary of the metrics"""
    
    print("=" * 60)
    if raw:
        print(f"📊 RAW DATA SUMMARY: {data['metadata']['repository']}")
        print(f"📅 Date: {data['metadata']['measurement_period']['start'][:10]}")
        print(f"⏰ Period: {data['metadata']['measurement_period']['start'][11:19]} - {data['metadata']['measurement_period']['end'][11:19]} IST")
        print("=" * 60)
        
        prs = data.get('prs', [])
        all_ai_comments = []
        for pr in prs:
            all_ai_comments.extend(pr.get('ai_comments', []))
        
        print(f"📈 PRs: {len(prs)}")
        print(f"💬 AI Comments: {len(all_ai_comments)}")
        print(f"🔧 System Events: {len(data.get('system_events', []))}")
        
        # Comment status breakdown
        active_comments = [c for c in all_ai_comments if c['status']['current'] == 'active']
        outdated_comments = [c for c in all_ai_comments if c['status']['current'] == 'outdated']
        
        print(f"\n📝 Comment Status:")
        print(f"   • Active: {len(active_comments)}")
        print(f"   • Outdated: {len(outdated_comments)}")
        
        # Reactions summary
        thumbs_up = sum(c['reactions']['thumbs_up'] for c in all_ai_comments)
        thumbs_down = sum(c['reactions']['thumbs_down'] for c in all_ai_comments)
        
        print(f"\n👍 Reactions:")
        print(f"   • Thumbs Up: {thumbs_up}")
        print(f"   • Thumbs Down: {thumbs_down}")
        
    else:
        print(f"📊 METRICS SUMMARY: {data['metadata']['repository']}")
        print(f"📅 Date: {data['metadata']['date']}")
        print("=" * 60)
        
        # Stats
        stats = data.get('stats', {})
        print(f"📊 STATS:")
        print(f"   • Total Comments: {stats.get('total_comments', 0)}")
        print(f"   • PRs Reviewed: {stats.get('prs_reviewed', 0)}")
        
        categories = stats.get('comment_categories', {})
        if categories:
            print(f"   • Categories: {', '.join(f'{k}({v})' for k, v in categories.items())}")
        
        severity = stats.get('severity_distribution', {})
        if severity:
            print(f"   • Severity: High({severity.get('high', 0)}) Low({severity.get('low', 0)})")
        
        # Effectiveness
        eff = data.get('effectiveness', {})
        print(f"\n🎯 EFFECTIVENESS:")
        print(f"   • Acceptance Rate: {eff.get('comment_acceptance_rate', 0)}%")
        print(f"   • Critical Issue Accepted: {eff.get('critical_issue_accepted_rate', eff.get('critical_issue_catch_rate', 0))}%")
        print(f"   • False Positive Rate: {eff.get('false_positive_rate', 0)}%")
        
        accuracy = eff.get('issue_detection_accuracy', {})
        if accuracy:
            print(f"   • F1-Score: {accuracy.get('f1_score', 0)}")
            print(f"   • Precision: {accuracy.get('precision', 0)}")
            print(f"   • Recall: {accuracy.get('recall', 0)}")
        
        # Productivity
        prod = data.get('productivity', {})
        print(f"\n⚡ PRODUCTIVITY:")
        print(f"   • Human Review Comment Percent: {prod.get('human_review_comment_percent', 0)}%")
        print(f"   • Time Saved: {prod.get('time_saved_minutes', 0)} minutes")
        print(f"   • Time Saved: {prod.get('time_saved_hours', 0)} hours")
        print(f"   • Feedback Quality: {prod.get('feedback_quality_rate', 0)}%")
        
        # Technical
        tech = data.get('technical', {})
        print(f"\n🔧 TECHNICAL:")
        print(f"   • System Uptime: {tech.get('system_uptime_percent', 0)}%")
        
        latency = tech.get('processing_latency', {})
        if latency:
            print(f"   • Processing Latency:")
            print(f"     - Small PRs: {latency.get('small_prs_median_minutes', 0)} min")
            print(f"     - Medium PRs: {latency.get('medium_prs_median_minutes', 0)} min")  
            print(f"     - Large PRs: {latency.get('large_prs_median_minutes', 0)} min")
    
    print("=" * 60)


def display_json(data: Dict[str, Any]):
    """Display data as formatted JSON"""
    print(json.dumps(data, indent=2))


def main():
    parser = argparse.ArgumentParser(description='View code review metrics')
    parser.add_argument('--repo', required=True, help='Repository name')
    parser.add_argument('--date', required=True, help='Date in YYYY-MM-DD format')
    parser.add_argument('--raw', action='store_true', help='Show raw data instead of metrics')
    parser.add_argument('--format', choices=['summary', 'json'], default='summary', 
                       help='Output format (default: summary)')
    
    args = parser.parse_args()
    
    try:
        # Load data
        data = load_metrics_data(args.repo, args.date, args.raw)
        
        # Display based on format
        if args.format == 'json':
            display_json(data)
        else:
            display_summary(data, args.raw)
            
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print(f"\n💡 Make sure to run the metrics generation script first:")
        print(f"   python scripts/generate_pg_router_metrics.py")
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON Error: {e}")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == '__main__':
    main()

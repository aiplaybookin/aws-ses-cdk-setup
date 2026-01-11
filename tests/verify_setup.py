import boto3
import time
from rich.console import Console
from rich.table import Table

console = Console()

def verify_ses_setup(domain, region='us-east-1'):
    """Verify SES setup is complete"""
    
    ses = boto3.client('ses', region_name=region)
    route53 = boto3.client('route53', region_name=region)
    
    console.print(f"\n[bold cyan]Verifying SES setup for {domain}...[/bold cyan]\n")
    
    # 1. Check domain verification
    console.print("[yellow]1. Checking domain verification...[/yellow]")
    try:
        response = ses.get_identity_verification_attributes(Identities=[domain])
        status = response['VerificationAttributes'].get(domain, {}).get('VerificationStatus')
        
        if status == 'Success':
            console.print(f"   ✓ Domain [green]{domain}[/green] is [bold green]verified[/bold green]")
        elif status == 'Pending':
            console.print(f"   ⏳ Domain verification is [yellow]pending[/yellow]")
            console.print("   Wait 10-15 minutes for DNS propagation")
        else:
            console.print(f"   ✗ Domain verification [red]failed[/red] or not started")
    except Exception as e:
        console.print(f"   ✗ Error: {e}")
    
    # 2. Check DKIM
    console.print("\n[yellow]2. Checking DKIM status...[/yellow]")
    try:
        response = ses.get_identity_dkim_attributes(Identities=[domain])
        dkim_attrs = response['DkimAttributes'].get(domain, {})
        
        if dkim_attrs.get('DkimEnabled') and dkim_attrs.get('DkimVerificationStatus') == 'Success':
            console.print("   ✓ DKIM is [bold green]enabled and verified[/bold green]")
        else:
            console.print(f"   Status: {dkim_attrs.get('DkimVerificationStatus', 'Unknown')}")
    except Exception as e:
        console.print(f"   ✗ Error: {e}")
    
    # 3. Check send quota
    console.print("\n[yellow]3. Checking send quota...[/yellow]")
    try:
        quota = ses.get_send_quota()
        
        table = Table(title="Send Quota")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Max 24hr Send", f"{quota['Max24HourSend']:,.0f}")
        table.add_row("Max Send Rate", f"{quota['MaxSendRate']}/second")
        table.add_row("Sent Last 24hr", f"{quota['SentLast24Hours']:,.0f}")
        table.add_row("Remaining", f"{quota['Max24HourSend'] - quota['SentLast24Hours']:,.0f}")
        
        console.print(table)
        
        if quota['Max24HourSend'] == 200:
            console.print("\n   ⚠️  Account is in [yellow]sandbox mode[/yellow]")
            console.print("   Request production access at: https://console.aws.amazon.com/ses/")
    except Exception as e:
        console.print(f"   ✗ Error: {e}")
    
    # 4. Check configuration set
    console.print("\n[yellow]4. Checking configuration set...[/yellow]")
    try:
        config_sets = ses.list_configuration_sets()
        if any(cs['Name'] == 'email-campaign-tracking' for cs in config_sets['ConfigurationSets']):
            console.print("   ✓ Configuration set [green]email-campaign-tracking[/green] exists")
        else:
            console.print("   ✗ Configuration set not found")
    except Exception as e:
        console.print(f"   ✗ Error: {e}")
    
    console.print("\n[bold green]✓ Verification complete![/bold green]\n")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python verify_setup.py yourdomain.com")
        sys.exit(1)
    
    verify_ses_setup(sys.argv[1])
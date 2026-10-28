"""Owner-side proxy check. Enter credentials privately; none are saved."""
import asyncio,getpass,json,ssl,time,ipaddress
async def main():
    import httpx
    from network import PublicProxy,parse_proxy,proxy_url
    address=getpass.getpass('Proxy address or Webshare export line (hidden): ')
    username=getpass.getpass('Username (empty if included): ')
    password=getpass.getpass('Password (empty if included): ')
    proxy=PublicProxy();proxy.upstream=parse_proxy(address,username,password)
    port=await proxy.start();started=time.monotonic()
    try:
        async with httpx.AsyncClient(proxy=f'http://127.0.0.1:{port}',trust_env=False,verify=ssl.create_default_context(),timeout=25) as client:
            response=await client.get('https://api.ipify.org?format=json');response.raise_for_status()
            exit_ip=str(ipaddress.ip_address(response.json()['ip']))
        print(json.dumps({'ok':True,'proxy':proxy_url(proxy.upstream),'exit_ip':exit_ip,'seconds':round(time.monotonic()-started,1)},ensure_ascii=False))
        return 0
    except Exception:
        print(json.dumps({'ok':False,'diagnostic':proxy.last_error or {'code':'PROXY_TEST_FAILED','message':'TLS or IP check failed; no direct fallback used'}},ensure_ascii=False))
        return 1
    finally:await proxy.close()
if __name__=='__main__':raise SystemExit(asyncio.run(main()))

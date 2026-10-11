"""Chromium desktop/mobile RU/EN UI; real SQLite/HTTPS, synthetic model."""
import argparse
import asyncio
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from check_storage import ROOT,manifest
from check_web_ui import certificate_pin


async def run(record,root):
    from playwright.async_api import async_playwright,expect
    sys.path.insert(0,str(ROOT/'tests'))
    from browser_fixture import BrowserFixture,PASSWORD
    fixture=BrowserFixture(root)
    try:
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(args=['--ignore-certificate-errors-spki-list='+certificate_pin(fixture.cert)])
            desktop=await browser.new_context(viewport={'width':1280,'height':850})
            page=await desktop.new_page();errors=[];external=[]
            page.on('pageerror',lambda _:errors.append(True))
            page.on('request',lambda r:external.append(True) if not r.url.startswith(fixture.url+'/') else None)
            await page.goto(fixture.url)
            await expect(page.locator('#login-button')).to_be_enabled()
            await page.locator('#login-language').select_option('en')
            await expect(page.locator('#login-button')).to_have_text('Sign in')
            record('english_login_labels',await page.locator('html').get_attribute('lang')=='en')
            await page.locator('#username').fill('ui-test');await page.locator('#password').fill(PASSWORD)
            await page.locator('#login-button').click();await expect(page.locator('#workspace')).to_be_visible()
            await page.locator('#ui-language').select_option('en')
            await expect(page.locator('#logout')).to_have_text('Sign out')
            await expect(page.locator('#reply-language')).to_be_enabled()
            record('interface_and_reply_are_independent',await page.locator('#reply-language').input_value()=='ru')
            await page.locator('#reply-language').select_option('en')
            await expect(page.locator('#reply-language')).to_be_enabled()
            record('preferences_persisted_on_server',fixture.repo.preferences(fixture.owner)['reply_language']=='en')
            await page.locator('#new-chat').click();await page.locator('#new-title').fill('Language UI control')
            await page.locator('#create-form button[type=submit]').click()
            await page.locator('#message-input').fill('Mixed-language synthetic question: Привет.')
            await page.locator('#send-button').click()
            await expect(page.locator('.message.assistant .message-state')).to_have_text('Reply saved',timeout=15000)
            record('english_reply_state_and_memory_labels',await page.locator('.memory-sources summary').count()==1)
            # Resolve the chat by route, never rely on timestamps/list ordering.
            chat=page.url.split('#chat=')[1].split('&')[0]
            record('explicit_reply_language_saved',fixture.repo.history(fixture.owner,chat)[-1].get('reply_language')=='en')
            raw=await page.locator('.message.assistant .message-text').text_content()
            url=page.url
            mobile=await browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,locale='ru-RU')
            phone=await mobile.new_page()
            phone.on('pageerror',lambda _:errors.append(True))
            phone.on('request',lambda r:external.append(True) if not r.url.startswith(fixture.url+'/') else None)
            await phone.goto(url)
            await expect(phone.locator('#login-button')).to_be_enabled()
            await phone.locator('#username').fill('ui-test');await phone.locator('#password').fill(PASSWORD)
            await phone.locator('#login-button').click();await expect(phone.locator('#workspace')).to_be_visible()
            await expect(phone.locator('#send-button')).to_have_text('Send')
            record('second_device_loads_server_language',await phone.locator('#reply-language').input_value()=='en')
            await phone.locator('#menu-button').click();await phone.locator('#ui-language').select_option('ru')
            await expect(phone.locator('#logout')).to_have_text('Выйти')
            await expect(phone.locator('#reply-language')).to_be_enabled()
            record('russian_ui_keeps_english_reply_setting',await phone.locator('#reply-language').input_value()=='en')
            await phone.locator('#drawer-backdrop').click()
            record('switch_does_not_translate_original_answer',await phone.locator('.message.assistant .message-text').text_content()==raw)
            await page.reload();await expect(page.locator('#send-button')).to_have_text('Отправить')
            record('saved_language_survives_reload',await page.locator('#reply-language').input_value()=='en')
            record('no_browser_storage',await page.evaluate('localStorage.length===0 && sessionStorage.length===0'))
            record('mobile_has_no_horizontal_overflow',await phone.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
            record('no_external_requests_or_javascript_errors',not external and not errors)
            await desktop.close();await mobile.close();await browser.close()
    finally:fixture.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    try:import playwright.async_api
    except ImportError:parser.error('Optional requirements.browser.lock and Chromium required')
    args.output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    try:fd=os.open(args.output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except OSError:parser.error('NEW report path required')
    source=manifest();started=time.monotonic()
    report={'format':'bublik-offline-check-v2','scope':'RU-EN-Chromium-desktop-mobile-TLS-synthetic-inference',
            'created_at':datetime.now(timezone.utc).isoformat(),'status':'failed','tests':[],
            'not_run':['real Qwen','physical Android/iPhone','mobile internet','Safari']}
    def record(name,passed):
        report['tests'].append({'id':name,'status':'passed' if passed else 'failed'})
        if not passed:raise RuntimeError('controlled_check_failed')
    with os.fdopen(fd,'w',encoding='utf-8') as stream:
        try:
            with tempfile.TemporaryDirectory(prefix='bublik-languages-ui-') as folder:asyncio.run(run(record,folder))
            report['status']='passed'
        except Exception as error:report['error_type']=type(error).__name__
        unchanged=source==manifest()
        if not unchanged:report['status']='failed'
        report['source']={'unchanged_during_run':unchanged,'source_sha256':source}
        report['summary']={'tests':len(report['tests']),'failures':sum(r['status']!='passed' for r in report['tests']),
                          'errors':int('error_type' in report),'skipped':0,'elapsed_seconds':time.monotonic()-started}
        json.dump(report,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'report':str(args.output),'status':report['status']}))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':sys.exit(main())

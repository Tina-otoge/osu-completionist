import logging
import os
from flask import url_for, redirect, request
import requests

from app import app

OSU_GET_TOKEN_URL = 'https://osu.ppy.sh/oauth/token'
OSU_AUTHORIZE_URL = 'https://osu.ppy.sh/oauth/authorize'
OSU_API_URL = 'https://osu.ppy.sh/api/v2'

def get_redirect():
    return url_for("auth", _external=True, _scheme='https' if request.headers.get('X-Forwarded-Proto') == 'https' else 'http')

def osu_call(url, token, data=None, method='GET'):
    if url.startswith('/'):
        url = f'{OSU_API_URL}{url}'
    return requests.request(method, url, data=data, params=data, headers={
        'Authorization': f'Bearer {token}'
    }).json()

@app.route('/login')
def login():
    token = request.cookies.get('token')
    if token:
        return redirect(url_for('index'))
    client_id = os.environ.get('OSU_CLIENT_ID')
    return f'<a href="{OSU_AUTHORIZE_URL}?client_id={client_id}&redirect_uri={get_redirect()}&response_type=code&scope=public">Login</a>'

@app.route('/auth')
def auth():
    client_id = os.environ.get('OSU_CLIENT_ID')
    client_secret = os.environ.get('OSU_CLIENT_SECRET')
    resp = requests.post(
        OSU_GET_TOKEN_URL,
        data=dict(
            client_id=client_id,
            client_secret=client_secret,
            code=request.args.get('code'),
            grant_type='authorization_code',
            redirect_uri=get_redirect(),
        )
    )
    if not resp.ok:
        logging.error(f'{resp} {resp.json()}')
        return 'An error occured during auth', 500
    token = resp.json().get('access_token')
    result = redirect(url_for('index'))
    result.set_cookie('token', token)
    return result

@app.route('/logout')
def logout():
    result = redirect(url_for('login'))
    result.set_cookie('token', '')
    return result

@app.route('/')
def index():
    token = request.cookies.get('token')
    if not token:
        return redirect(url_for('login'))
    user = osu_call('/me', token=token)
    is_supporter = user.get('is_supporter', False)
    if not is_supporter:
        return 'You must be an osu! supporter to access this data'
    search_all = osu_call('/beatmapsets/search/', token=token, data={
        'm': 0,
    })
    search_unplayed = osu_call('/beatmapsets/search/', token=token, data={
        'm': 0,
        'played': 'unplayed'
    })
    username = user.get("username")
    with open(f'{username}.json', 'w') as f:
        import json
        json.dump(search_unplayed, f, indent=2)
    maps = '<table>{}</table>'.format(
        ''.join([
            f'<tr><td><a href="https://osu.ppy.sh/beatmapsets/{x["id"]}">{x["artist"]} - {x["title"]} (mapped by {x["creator"]})</a></td><td><a href="osu://s/{x["id"]}">osu!direct</a></td></tr>'
            for x in search_unplayed.get('beatmapsets', [])
        ])
    )
    return f'''
        <!doctype html>
        <title>osu! completionist by Tina</title>
        Logged in as {username} | <a href="{url_for('logout')}">Logout</a><br>
        Unplayed mapsets: {search_unplayed.get("total")} / {search_all.get("total")}<br>
        Some unplayed maps:<br>
        {maps}
    '''

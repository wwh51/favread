# -*- coding: utf-8 -*-

from datetime import datetime
from weibo import APIClient
from sinaweibo.tools import *
from sinaweibo.models import User
from sinaweibo.config import *

def crawl_weibo_task():
    server = APIClient(app_key=APP_KEY, app_secret=APP_SECRET, redirect_uri=CALLBACK_URL)
    users = User.objects.all()
    for user in users:
        print u'crawler: [%d] last sync: %s' % (
            user.id, str(user.last_sync)[5:19]),
        server.set_access_token(user.auth_token, user.expired_time)
        print 'update statuses...'
        crawl_user(server, user, 50)

def crawl_user(server, user, count=50):
    try:
        favlist = server.favorites.ids.get(uid=user.id)
        server_count = favlist['total_number']

        if server_count == 0: return 0

        total_page = get_total_page(server_count, count)

        print 'crawl new favs', crawl_new_favorites(server, user, total_page, count)
        #print 'crawl del favs', crawl_del_favorites(server, user, total_page, count)

        user.last_sync = datetime.today()
        user.save()

    except Exception, e:
        print e
        return -1

def get_total_page(server_count, count=50):

    total_page = server_count / count + 1
    if server_count % count != 0: total_page = total_page + 1

    return total_page


def crawl_new_favorites(server, user, total_page, count=50):

    compare_date = user.last_sync   # 记录上次同步的时间点用于比较是否抓取完成
    new_count = 0                   # 新增的条目数

    for i in range(1, total_page):

        statuses = server.favorites.get(uid=user.id, page=i, count=count)
        page_first_time = str2datetime(statuses['favorites'][0]['favorited_time'])

        if page_first_time < compare_date: return new_count

        for status in statuses['favorites']:
            if compare_date > str2datetime(status['favorited_time']): return new_count

            #print 'saving status: %d' % status['status']['id']
            new_count = new_count + 1
            user.save_status(status)

    return new_count

def crawl_del_favorites(server, user, total_page, count=50):
    #TODO：处理抓取中服务器收藏修改的问题
    # 可以通过json的total_number解决？
    client_statuses = user.get_all_status(archived=None, destroyed=False)
    client_count = len(client_statuses)
    #print client_count, server_count
    client_index = 0

    del_count = 0

    for i in range(1, total_page):
        server_statuses = server.favorites.get(uid=user.id, page=i, count=count)
        server_count = server_statuses['total_number']
        server_index = 0

        while client_count != server_count and server_index < len(server_statuses['favorites']):
            ss = server_statuses['favorites'][server_index]
            cs = client_statuses[client_index]

            ssid = ss['status']['id']
            csid = cs.status.id

            if ssid == csid:
                server_index = server_index + 1
                client_index = client_index + 1

            elif str2datetime(ss['favorited_time']) < cs.fav_time:
                user.destroy_status(status_id=csid)

                del_count = del_count + 1
                
                client_count = client_count - 1
                client_index = client_index + 1
            else:
                server_index = server_index + 1

        if client_count == server_count: return del_count

    # weibo api 可能会出现统计的总数跟实际收藏数目不符合的问题。
    # 需要扩展当前数据库（增加一个offset）以实现对应的需求。
    # print client_count, server_count
    return del_count

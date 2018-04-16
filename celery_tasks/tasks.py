# 使用celery
from django.core.mail import send_mail
from django.conf import settings
from celery import Celery
import time

from django.template import loader,RequestContext


# 在任务处理者一端加这几句
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")
django.setup()

from apps.goods.models import GoodsType,GoodsSKU,IndexTypeGoodsBanner,IndexPromotionBanner,IndexGoodsBanner

# 创建一个Celery类的实例对象,连接第8个redis数据库
app = Celery('celery_tasks.tasks', broker='redis://127.0.0.1:6379/8')


# 定义任务函数
@app.task
def send_register_active_email(to_email, username, token):
    '''发送激活邮件'''
    # 组织邮件信息
    subject = '天天生鲜欢迎信息'
    message = ''
    sender = settings.EMAIL_FROM
    receiver = [to_email]
    html_message = '<h1>%s, 欢迎您成为天天生鲜注册会员</h1>请点击下面链接激活您的账户<br/><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>' % (username, token, token)

    send_mail(subject, message, sender, receiver, html_message=html_message)
    time.sleep(5)

@app.task
def generate_static_index_html():

    types = GoodsType.objects.all()
    goods_banners = IndexGoodsBanner.objects.all().order_by('index')
    promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

    for type in types:
        image_banners = IndexTypeGoodsBanner.objects.filter(type=type,display_type=1).order_by('index')
        title_banners = IndexTypeGoodsBanner.objects.filter(type=type,display_type=0).order_by('index')

        # 动态增加属性
        type.image_banners = image_banners
        type.title_banners = title_banners

    context = {'types':types,
               'goods_banner':goods_banners,
               'promotion_banners':promotion_banners}
    # 加载模板文件 返回模板对象
    temp = loader.get_template('static_base.html')
    # 模板渲染
    static_index_html = temp.render(context)

    # 生成首页静态文件
    save_path = os.path.join(settings.BASE_DIR,'static/index.html')

    with open(save_path,'w') as f:
        f.write(static_index_html)

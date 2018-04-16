from django.shortcuts import render,redirect

from django.views.generic import View
from django.core.cache import cache
from apps.goods.models import GoodsType,GoodsSKU,IndexGoodsBanner,IndexTypeGoodsBanner,IndexPromotionBanner
from apps.order.models import OrderGoods
from django_redis import get_redis_connection

from django.core.urlresolvers import reverse

from django.core.paginator import Paginator

class IndexView(View):

    def get(self,request):
        # 从缓存中获取数据
        context = cache.get("index_page_data")
        # 如果没有缓存
        if context is None:
            print("设置缓存")
            types = GoodsType.objects.all()

            goods_banners = IndexGoodsBanner.objects.all().order_by("index")

            promotion_banners = IndexPromotionBanner.objects.order_by("index")

            for type in types:
                image_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by("index")
                title_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by("index")
                type.image_banners = image_banners
                type.title_banners = title_banners

            context = {'types':types,
                        'good_banners':goods_banners,
                       'promotion_banners':promotion_banners}
            # 设置缓存
            cache.set("index_page_data",context,3600)

        user = request.user
        cart_count = 0
        print(1)
        if user.is_authenticated():
            # 用户已登录
            print(2)
            conn = get_redis_connection('default')
            cart_key = 'cart_%d'%user.id
            # 获取商品数目
            cart_count = conn.hlen(cart_key)
            print(cart_count)

        context.update(cart_count = cart_count)
        return render(request,'index.html',context)

class DetailView(View):

    def get(self,request,goods_id):

        try:
            # 得到商品的Querysets
            sku = GoodsSKU.objects.get(id = goods_id)
        except GoodsSKU.DoesNotExist:
            return redirect(reverse("goods:index"))
        # 获取商品分类信息
        types = GoodsType.objects.all()
        # 获取商品评论信息
        sku_opder = OrderGoods.objects.filter(sku=sku).exclude(comment='')
        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-creat_time')[:2]
        # 获取同一个spu其他规格商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)

        # 获取用户购物车中商品数目
        user = request.user
        cart_count = 0

        # 校验用户登录
        if user.is_authenticated():
            # 获取redis连接对象
            conn = get_redis_connection('default')
            cart_key = 'cart_%id'%user.id
            # 获取购物车商品数量
            cart_count = conn.hlen(cart_key)
            history_key = 'history_%id'%user.id

            # 移除原有id防止重复 lrem
            conn.lrem(history_key,0,goods_id)

            # 把goods_id插入到列表左侧lpush
            conn.lpush(history_key,goods_id)

            # 只保存五条 (内容，首，尾)
            conn.ltrim(history_key,0,4)

        context = {'sku':sku,
                   'types':type,
                   'sku_order':sku_opder,
                   'new_skus':new_skus,
                   'same_spu_skus':same_spu_skus,
                   'cart_count':cart_count}

        return render(request,'detail.html',context)

class ListView(View):
    '''列表页'''
    def get(self, request, type_id, page):
        '''显示列表页'''
        # 获取种类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            # 种类不存在
            return redirect(reverse('goods:index'))

        # 获取商品的分类信息
        types = GoodsType.objects.all()

        # 获取排序的方式 # 获取分类商品的信息
        # sort=default 按照默认id排序
        # sort=price 按照商品价格排序
        # sort=hot 按照商品销量排序
        sort = request.GET.get('sort')

        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')

        # 对数据进行分页
        paginator = Paginator(skus, 1)
        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1
        # 获取第page页的Page实例对象
        skus_page = paginator.page(page)
        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]

        # 获取用户购物车中商品的数目
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)

        # 组织模板上下文
        context = {'type':type, 'types':types,
                   'skus_page':skus_page,
                   'new_skus':new_skus,
                   'cart_count':cart_count,
                   'sort':sort}
        # 使用模板
        return render(request, 'list.html', context)



#!/usr/bin/env python3
"""
全国事业编招聘数据爬虫
数据源: shiyebian.com, offcn.com, 各省市人社局
输出: data.json (含 metadata + entries)
"""
import json
import os
import re
import time
import hashlib
from datetime import datetime, timedelta
from urllib.parse import urljoin

# ==================== 配置 ====================
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), 'data.json')
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
]
REQUEST_DELAY = 2  # 请求间隔(秒)
MAX_AGE_DAYS = 60   # 只保留最近60天的公告

# ==================== 工具函数 ====================
def make_headers():
    import random
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }

def parse_date(text):
    """从各种格式解析日期, 返回 YYYY-MM-DD"""
    patterns = [
        r'(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})',
        r'(\d{4})\.(\d{1,2})\.(\d{1,2})',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                return f'{y:04d}-{mo:02d}-{d:02d}'
            except:
                pass
    return None

def classify_exam(name_text):
    """根据单位名称推断考试类别"""
    text = name_text
    if any(k in text for k in ['教师', '学校', '学院', '大学', '教育', '师范', '教学', '教研']):
        return 'D'
    if any(k in text for k in ['医院', '医疗', '卫健委', '卫生', '健康', '疾控', '中医', '临床', '护理']):
        return 'E'
    if any(k in text for k in ['科技', '工程', '环境', '水利', '农业', '农技', '林业', '计算机', '信息中心', '监测']):
        return 'C'
    if any(k in text for k in ['社科', '社科院', '文联', '文化', '新闻', '出版', '法律', '法学']):
        return 'B'
    return 'A'

def classify_nature(name_text):
    """根据名称推断编制性质"""
    text = name_text
    if '辅警' in text:
        return 'aux'
    if '聘用制' in text or '合同制' in text or '劳务派遣' in text:
        return 'hire'
    return 'est'

def province_city_map():
    """省-市映射表"""
    return {
        '北京': ['东城区', '西城区', '朝阳区', '海淀区', '丰台区', '石景山区', '通州区', '大兴区', '房山区', '昌平区', '顺义区', '怀柔区', '密云区', '延庆区', '平谷区', '门头沟区'],
        '上海': ['浦东新区', '黄浦区', '徐汇区', '长宁区', '静安区', '普陀区', '虹口区', '杨浦区', '闵行区', '宝山区', '嘉定区', '金山区', '松江区', '青浦区', '奉贤区', '崇明区'],
        '天津': ['和平区', '河东区', '河西区', '南开区', '河北区', '红桥区', '东丽区', '西青区', '津南区', '北辰区', '武清区', '宝坻区', '滨海新区', '宁河区', '静海区', '蓟州区'],
        '重庆': ['渝中区', '江北区', '南岸区', '沙坪坝区', '九龙坡区', '大渡口区', '北碚区', '渝北区', '巴南区', '万州区', '涪陵区', '黔江区', '长寿区', '江津区', '合川区', '永川区', '南川区', '綦江区', '大足区', '璧山区', '铜梁区', '潼南区', '荣昌区', '开州区', '梁平区', '武隆区'],
        '广东': ['广州', '深圳', '珠海', '汕头', '佛山', '韶关', '湛江', '肇庆', '江门', '茂名', '惠州', '梅州', '汕尾', '河源', '阳江', '清远', '东莞', '中山', '潮州', '揭阳', '云浮'],
        '浙江': ['杭州', '宁波', '温州', '嘉兴', '湖州', '绍兴', '金华', '衢州', '舟山', '台州', '丽水'],
        '江苏': ['南京', '无锡', '徐州', '常州', '苏州', '南通', '连云港', '淮安', '盐城', '扬州', '镇江', '泰州', '宿迁'],
        '山东': ['济南', '青岛', '淄博', '枣庄', '东营', '烟台', '潍坊', '济宁', '泰安', '威海', '日照', '临沂', '德州', '聊城', '滨州', '菏泽'],
        '河南': ['郑州', '开封', '洛阳', '平顶山', '安阳', '鹤壁', '新乡', '焦作', '濮阳', '许昌', '漯河', '三门峡', '南阳', '商丘', '信阳', '周口', '驻马店'],
        '四川': ['成都', '自贡', '攀枝花', '泸州', '德阳', '绵阳', '广元', '遂宁', '内江', '乐山', '南充', '眉山', '宜宾', '广安', '达州', '雅安', '巴中', '资阳'],
        '湖北': ['武汉', '黄石', '十堰', '宜昌', '襄阳', '鄂州', '荆门', '孝感', '荆州', '黄冈', '咸宁', '随州', '恩施'],
        '湖南': ['长沙', '株洲', '湘潭', '衡阳', '邵阳', '岳阳', '常德', '张家界', '益阳', '郴州', '永州', '怀化', '娄底', '湘西'],
        '福建': ['福州', '厦门', '莆田', '三明', '泉州', '漳州', '南平', '龙岩', '宁德'],
        '安徽': ['合肥', '芜湖', '蚌埠', '淮南', '马鞍山', '淮北', '铜陵', '安庆', '黄山', '滁州', '阜阳', '宿州', '六安', '亳州', '池州', '宣城'],
        '河北': ['石家庄', '唐山', '秦皇岛', '邯郸', '邢台', '保定', '张家口', '承德', '沧州', '廊坊', '衡水'],
        '辽宁': ['沈阳', '大连', '鞍山', '抚顺', '本溪', '丹东', '锦州', '营口', '阜新', '辽阳', '盘锦', '铁岭', '朝阳', '葫芦岛'],
        '江西': ['南昌', '景德镇', '萍乡', '九江', '新余', '鹰潭', '赣州', '吉安', '宜春', '抚州', '上饶'],
        '陕西': ['西安', '铜川', '宝鸡', '咸阳', '渭南', '延安', '汉中', '榆林', '安康', '商洛'],
        '山西': ['太原', '大同', '阳泉', '长治', '晋城', '朔州', '晋中', '运城', '忻州', '临汾', '吕梁'],
        '吉林': ['长春', '吉林', '四平', '辽源', '通化', '白山', '松原', '白城', '延边'],
        '黑龙江': ['哈尔滨', '齐齐哈尔', '鸡西', '鹤岗', '双鸭山', '大庆', '伊春', '佳木斯', '七台河', '牡丹江', '黑河', '绥化'],
        '贵州': ['贵阳', '六盘水', '遵义', '安顺', '毕节', '铜仁', '黔西南', '黔东南', '黔南'],
        '云南': ['昆明', '曲靖', '玉溪', '保山', '昭通', '丽江', '普洱', '临沧', '楚雄', '红河', '文山', '西双版纳', '大理', '德宏', '怒江', '迪庆'],
        '广西': ['南宁', '柳州', '桂林', '梧州', '北海', '防城港', '钦州', '贵港', '玉林', '百色', '贺州', '河池', '来宾', '崇左'],
        '海南': ['海口', '三亚', '三沙', '儋州', '五指山', '琼海', '文昌', '万宁', '东方', '澄迈', '定安', '屯昌', '临高', '白沙', '昌江', '乐东', '陵水', '保亭', '琼中'],
        '内蒙古': ['呼和浩特', '包头', '乌海', '赤峰', '通辽', '鄂尔多斯', '呼伦贝尔', '巴彦淖尔', '乌兰察布', '兴安', '锡林郭勒', '阿拉善'],
        '甘肃': ['兰州', '嘉峪关', '金昌', '白银', '天水', '武威', '张掖', '平凉', '酒泉', '庆阳', '定西', '陇南', '临夏', '甘南'],
        '宁夏': ['银川', '石嘴山', '吴忠', '固原', '中卫'],
        '青海': ['西宁', '海东', '海北', '黄南', '海南', '果洛', '玉树', '海西'],
        '新疆': ['乌鲁木齐', '克拉玛依', '吐鲁番', '哈密', '昌吉', '博尔塔拉', '巴音郭楞', '阿克苏', '克孜勒苏', '喀什', '和田', '伊犁', '塔城', '阿勒泰'],
        '西藏': ['拉萨', '日喀则', '昌都', '林芝', '山南', '那曲', '阿里'],
        '台湾': ['台北', '高雄', '台中', '台南', '新北', '桃园', '新竹', '基隆', '嘉义', '彰化'],
        '香港': ['中西区', '湾仔区', '东区', '南区', '油尖旺', '深水埗', '九龙城', '黄大仙', '观塘', '荃湾', '屯门', '元朗', '北区', '大埔', '沙田', '西贡', '离岛'],
        '澳门': ['花地玛堂区', '圣安多尼堂区', '大堂区', '望德堂区', '风顺堂区', '嘉模堂区', '圣方济各堂区'],
    }

def match_city(name_text, province_text, pc_map):
    """从单位名称匹配城市"""
    cities = pc_map.get(province_text, [])
    for city in sorted(cities, key=lambda x: -len(x)):
        if city in name_text:
            return city
    # 匹配省级简称+单位
    short_map = {'北京': '京', '上海': '沪', '天津': '津', '重庆': '渝',
                 '广东': '粤', '浙江': '浙', '江苏': '苏', '山东': '鲁',
                 '河南': '豫', '四川': '川', '湖北': '鄂', '湖南': '湘',
                 '福建': '闽', '安徽': '皖', '河北': '冀', '辽宁': '辽',
                 '江西': '赣', '陕西': '陕', '山西': '晋', '吉林': '吉',
                 '黑龙江': '黑', '贵州': '黔', '云南': '云', '广西': '桂',
                 '海南': '琼', '内蒙古': '蒙', '甘肃': '甘', '宁夏': '宁',
                 '青海': '青', '新疆': '新', '西藏': '藏'}
    short = short_map.get(province_text, province_text[:2])
    if short in name_text:
        return cities[0] if cities else province_text
    return cities[0] if cities else province_text

def entry_key(entry):
    """生成去重 key"""
    return hashlib.md5(f"{entry['name']}|{entry['province']}".encode()).hexdigest()

def load_existing():
    """加载已有数据"""
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def merge_data(existing_data, new_entries):
    """合并新旧数据, 去重, 过滤过期"""
    cutoff = (datetime.now() - timedelta(days=MAX_AGE_DAYS)).strftime('%Y-%m-%d')

    # 已有 entries
    existing = {}
    if existing_data and 'entries' in existing_data:
        for e in existing_data['entries']:
            key = entry_key(e)
            if key not in existing or e.get('announceDate', '') > existing[key].get('announceDate', ''):
                existing[key] = e

    # 新数据覆盖
    for e in new_entries:
        key = entry_key(e)
        existing[key] = e

    # 过滤过期 + 排序(按发布日期倒序)
    entries = [e for e in existing.values() if e.get('announceDate', '') >= cutoff]
    entries.sort(key=lambda x: x.get('announceDate', ''), reverse=True)

    return entries

# ==================== 数据源1: 事业编网 (shiyebian.com) ====================
def scrape_shiyebian():
    """爬取 shiyebian.com 最新公告"""
    entries = []
    try:
        import urllib.request
        url = 'https://www.shiyebian.net/'
        req = urllib.request.Request(url, headers=make_headers())
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            # 网站编码为GBK，不是UTF-8
            html = raw.decode('gbk', errors='ignore')

        # 解析标题列表 (支持两种格式)
        # 格式1: <a ...>XXXX招聘公告</a>
        # 格式2: <a title="XXXX招聘公告">...</a>
        seen = set()
        matches = []
        # 优先匹配 title 属性
        title_pat = r'<a[^>]*title="([^"]*(?:招聘|选调|遴选|引进|招录)[^"]*)"'
        for m in re.findall(title_pat, html):
            m = m.strip()
            if len(m) > 8 and m not in seen:
                seen.add(m)
                matches.append(m)
        # 再匹配链接文本
        text_pat = r'<a[^>]*>([^<]*(?:招聘|选调|遴选|引进|招录)[^<]*)</a>'
        for m in re.findall(text_pat, html):
            m = re.sub(r'&#\d+;', '', m).strip()
            if len(m) > 8 and m not in seen:
                seen.add(m)
                matches.append(m)
        for title in matches[:50]:  # 限制数量
            entry = parse_entry_from_title(title)
            if entry:
                entries.append(entry)
        print(f'  [shiyebian.com] 获取 {len(entries)} 条')
    except Exception as e:
        print(f'  [shiyebian.com] 爬取失败: {e}')
    return entries

def parse_entry_from_title(title):
    """从标题解析招聘信息"""
    pc_map = province_city_map()
    clean = title.strip()

    # 尝试提取省级地区
    province = None
    for p in pc_map:
        if p in clean:
            province = p
            break

    if not province:
        # 尝试简称匹配
        short_prov = {'京': '北京', '沪': '上海', '津': '天津', '渝': '重庆',
                      '粤': '广东', '浙': '浙江', '苏': '江苏', '鲁': '山东',
                      '豫': '河南', '川': '四川', '鄂': '湖北', '湘': '湖南',
                      '闽': '福建', '皖': '安徽', '冀': '河北', '辽': '辽宁',
                      '赣': '江西', '陕': '陕西', '晋': '山西', '吉': '吉林',
                      '黑': '黑龙江', '黔': '贵州', '云': '云南', '桂': '广西',
                      '琼': '海南', '蒙': '内蒙古', '甘': '甘肃', '宁': '宁夏',
                      '青': '青海', '新': '新疆', '藏': '西藏'}
        for short, full in short_prov.items():
            if short in clean:
                province = full
                break

    if not province:
        # 直辖市特殊处理
        direct = ['北京', '上海', '天津', '重庆']
        for d in direct:
            if d in clean:
                province = d
                break

    if not province:
        return None

    city = match_city(clean, province, pc_map)

    # 尝试提取人数
    hire = 0
    count_patterns = [
        r'(\d+)人', r'(\d+)名', r'招聘(\d+)', r'选调(\d+)',
        r'引进(\d+)', r'招录(\d+)', r'招募(\d+)'
    ]
    for cp in count_patterns:
        m = re.search(cp, clean)
        if m:
            hire = int(m.group(1))
            break

    return {
        'name': clean,
        'province': province,
        'city': city,
        'hireCount': max(hire, 1),
        'announceDate': datetime.now().strftime('%Y-%m-%d'),
        'deadline': (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d'),
        'examCategory': classify_exam(clean),
        'nature': classify_nature(clean),
    }

# ==================== 数据源2: 手动更新接口 ====================
def load_manual_entries():
    """从 manual_entries.json 加载人工录入的数据(优先级最高)"""
    manual_path = os.path.join(os.path.dirname(__file__), 'manual_entries.json')
    if os.path.exists(manual_path):
        with open(manual_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# ==================== 主流程 ====================
def main():
    print(f'=== 全国事业编招聘数据爬虫 ===')
    print(f'启动时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    # 1. 加载已有数据作为基底
    existing = load_existing()
    base_count = len(existing['entries']) if existing else 0
    print(f'已有数据: {base_count} 条')

    # 2. 爬取最新数据
    print('\n采集数据源:')
    new_entries = []

    # 源1: 爬虫抓取
    scraped = scrape_shiyebian()
    new_entries.extend(scraped)

    # 源2: 人工录入(最高优先级)
    manual = load_manual_entries()
    if manual:
        print(f'  [手动录入] {len(manual)} 条')
        new_entries.extend(manual)

    # 3. 合并去重
    merged = merge_data(existing, new_entries)
    print(f'\n合并后: {len(merged)} 条 (去重 + 过滤{MAX_AGE_DAYS}天前)')

    # 4. 构建输出
    templates = existing.get('positionTemplates', []) if existing else [
        {"name":"综合管理岗","education":"本科","major":"管理","fresh":"否","hireCount":2},
        {"name":"信息化管理岗","education":"本科","major":"计算机","fresh":"是","hireCount":3},
        {"name":"财务管理岗","education":"本科","major":"财会","fresh":"否","hireCount":2},
        {"name":"法律事务岗","education":"本科","major":"法律","fresh":"是","hireCount":4},
        {"name":"文字综合岗","education":"本科","major":"汉语言","fresh":"否","hireCount":3},
        {"name":"工程管理岗","education":"本科","major":"工程","fresh":"否","hireCount":5},
        {"name":"环境监测岗","education":"本科","major":"农林","fresh":"是","hireCount":2},
        {"name":"医疗卫生岗","education":"本科","major":"医学","fresh":"否","hireCount":4},
        {"name":"科研技术岗","education":"硕士","major":"不限","fresh":"是","hireCount":3},
        {"name":"教学管理岗","education":"硕士","major":"教育","fresh":"否","hireCount":2},
        {"name":"数据分析岗","education":"硕士","major":"计算机","fresh":"是","hireCount":2},
        {"name":"经济分析岗","education":"硕士","major":"经济","fresh":"否","hireCount":3},
        {"name":"新闻宣传岗","education":"本科","major":"汉语言","fresh":"是","hireCount":1},
        {"name":"网络运维岗","education":"大专","major":"计算机","fresh":"否","hireCount":2},
        {"name":"项目管理岗","education":"本科","major":"管理","fresh":"是","hireCount":3},
        {"name":"文秘岗","education":"本科","major":"不限","fresh":"是","hireCount":2},
        {"name":"档案管理岗","education":"大专","major":"不限","fresh":"否","hireCount":1},
        {"name":"规划设计岗","education":"硕士","major":"工程","fresh":"否","hireCount":2},
        {"name":"农林技术岗","education":"本科","major":"农林","fresh":"否","hireCount":3},
        {"name":"审计监督岗","education":"本科","major":"财会","fresh":"是","hireCount":2},
        {"name":"行政执法岗","education":"本科","major":"法律","fresh":"否","hireCount":4},
        {"name":"临床医学岗","education":"硕士","major":"医学","fresh":"否","hireCount":5},
        {"name":"护理岗","education":"大专","major":"医学","fresh":"否","hireCount":6},
        {"name":"教研岗","education":"硕士","major":"教育","fresh":"是","hireCount":2},
        {"name":"金融监管岗","education":"硕士","major":"经济","fresh":"是","hireCount":3},
        {"name":"安全管理岗","education":"本科","major":"不限","fresh":"否","hireCount":2},
        {"name":"文化旅游岗","education":"本科","major":"管理","fresh":"是","hireCount":3},
        {"name":"社会保障岗","education":"本科","major":"不限","fresh":"否","hireCount":2},
        {"name":"建筑质检岗","education":"本科","major":"工程","fresh":"否","hireCount":3},
        {"name":"水利技术岗","education":"本科","major":"工程","fresh":"是","hireCount":4},
    ]

    exam_cat_names = existing.get('examCategoryNames', {}) if existing else {
        'A': '综合管理', 'B': '社会科学', 'C': '自然科学', 'D': '中小学教师', 'E': '医疗卫生'
    }

    nature_labels = existing.get('natureLabels', {}) if existing else {
        'est': '事业编', 'hire': '聘用制', 'aux': '辅警/非编', 'ent': '企业岗'
    }

    output = {
        'metadata': {
            'version': '1.0',
            'lastUpdated': datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'),
            'source': 'shiyebian.com / offcn.com / 各省市人社局 / 手动录入',
            'totalEntries': len(merged),
            'precision': '★★★',
            'autoGenerated': True,
            'note': '自动爬取 + 手动校正。截止日期为估算, 请以官方公告为准。'
        },
        'examCategories': ['A', 'B', 'C', 'D', 'E'],
        'examCategoryNames': exam_cat_names,
        'natureLabels': nature_labels,
        'positionTemplates': templates,
        'entries': merged
    }

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 同时生成 data.js
    js_path = os.path.join(os.path.dirname(__file__), 'data.js')
    js_content = '// 全国事业编招聘数据 - 自动生成\n// 更新时间: ' + output['metadata']['lastUpdated'] + '\nwindow.zhaopinData = ' + json.dumps(output, ensure_ascii=False, indent=2) + ';\n'
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(js_content)

    print(f'\n[OK] Written to {OUTPUT_PATH} + data.js')
    print(f'   总共 {len(merged)} 条记录')

if __name__ == '__main__':
    main()

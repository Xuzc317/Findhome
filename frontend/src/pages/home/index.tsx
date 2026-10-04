import Header, { showCityModal } from "@/components/header";
import styles from "./styles.module.scss";
import { Button, Carousel } from "antd";
import { HOME_CITIES } from "./config";
import { useNavigate } from "react-router-dom";

const Home = () => {
  return (
    <>
      <div className={styles.container}>
        <Header
          style={{
            background: "#1a1f2a",
          }}
        ></Header>
        <div className={styles.content}>
          <CarouselContainer />
          <Banner />
          <Introduction />
          <Thanks />
          <Contact />
        </div>
      </div>
      <Footer />
    </>
  );
};

function CarouselContainer() {
  return (
    <div className={styles["carousel-wrap"]}>
      <Carousel autoplay>
        <a href="https://chat.r2049.cn/user/login" target="_blank" className={styles["carousel-item"]}>
          GPT2077：注册直送50W Token额度（GPT4、3.5模型通用）。
        </a>
        <a href="https://pdf.r2049.cn/?lang=zh_CN" target="_blank" className={styles["carousel-item"]}>
          R2049 PDF：免安装在线PDF工具集~
        </a>
        <a href="https://mp.weixin.qq.com/s/4nC2zZm2a6Tn4LL7H-oC8w" target="_blank" className={styles["carousel-item"]}>
          关注【人生删除指南】微信公众号获取租房小程序。
        </a>
        <a href="https://wj.qq.com/s/2953926/aabe" target="_blank" className={styles["carousel-item"]}>
          帮我们做得更好?
        </a>
        <a href="https://wj.qq.com/s2/3264919/3fdd" target="_blank" className={styles["carousel-item"]}>
          合租需谨慎，群租有风险，长租公寓多当心。
        </a>
      </Carousel>
    </div>
  );
}

function Banner() {
  const navigate = useNavigate();
  return (
    <div className={styles.banner}>
      <div>
        <h2 className={styles.slogan}>满大街找租房心力交瘁？试试换个方式直接在地图上搜租房!</h2>
        <p className={styles["sub-slogan"]}>多平台房源爬虫 + 在线地图强力驱动,帮助你迅速找到合适房源。</p>
        <p className={styles["sub-slogan"]}>
          微信小程序"地图搜租房"已上线，欢迎关注【人生删除指南】微信公众号体验反馈。
        </p>
        <Button
          danger
          type="primary"
          className={styles["start"]}
          onClick={() => {
            navigate("/houses-list");
          }}
        >
          马上开始
        </Button>
      </div>
    </div>
  );
}

function Introduction() {
  const navigate = useNavigate();
  return (
    <div className={styles["introduction"]}>
      <div>
        <h3 className={styles["sub-title"]}>这是什么？</h3>
        <p className={styles["text"]}>
          通过实时爬虫获取公开租房信息，直接在高德地图上直观展示房源位置+基础信息，同时提供住址到公司的路线计算（公交+地图
          or
          步行导航），已实现【豆瓣租房小组】、【Zuber合租】、【蘑菇租房】、【58品牌公寓/安选】、【Hi住租房】、【房多多】、【贝壳租房】、【v2ex租房帖子】、【自如/青客/城家】等房源信息数据爬取，部分房源价格支持筛选功能。
          点击此处查看
          <a
            href="https://github.com/liguobao/HouseSearch/blob/master/%E4%BD%BF%E7%94%A8%E6%95%99%E7%A8%8B.md"
            className={styles["highlight-name"]}
          >
            【使用教程.md】
          </a>
          (PS:手机端地图查看房源信息不太友好,建议使用PC浏览器.)
        </p>
        <div className={styles["cities"]}>
          {HOME_CITIES.map((item) => {
            return (
              <div className={styles["city-item"]}>
                <div
                  onClick={() => {
                    navigate(`/houses-list?city=${item.cityname}`);
                  }}
                  className={styles["highlight-name"]}
                >
                  {item.name}
                </div>
                <div className={styles["form"]}>
                  {item.form?.map((where, index) => {
                    return (
                      <span
                        onClick={() => {
                          navigate(`/houses-list?city=${item.cityname}&source=${where.source}`);
                        }}
                        className={styles["highlight-name"]}
                      >
                        {where.name + (index === item.form.length - 1 ? "" : "、")}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}

          <div className={styles["city-item"]}>
            <div
              className={styles["highlight-name"]}
              onClick={() => {
                showCityModal();
              }}
            >
              更多城市
            </div>
            <div className={styles["form"]}>
              <span
                onClick={() => {
                  navigate("/houses-list?city=成都");
                }}
                className={styles["highlight-name"]}
              >
                成都、
              </span>
              <span
                onClick={() => {
                  navigate("/houses-list?city=杭州");
                }}
                className={styles["highlight-name"]}
              >
                杭州、
              </span>
              <span
                onClick={() => {
                  navigate("/houses-list?city=厦门");
                }}
                className={styles["highlight-name"]}
              >
                厦门...
              </span>
            </div>
          </div>
          <div className={`${styles["city-item"]} ${styles["search"]}`}>
            <div
              className={styles["highlight-name"]}
              onClick={() => {
                // "toggleDialog('searchVisible', true)"
              }}
            >
              高级搜索
            </div>
            <p>支持关键字 + 信息来源 + 发布日期组合搜索</p>
          </div>
        </div>
        <div className={`${styles["new-douban"]} ${styles["running"]}`}>
          <div
            className={styles["highlight-name"]}
            onClick={() => {
              // "toggleDialog('doubanAddVisible', true)"
            }}
          >
            新增租房数据源？
          </div>
          <p>你在的城市没有数据？没有对应的租房小组数据？请联系公众号【人生删除指南】或者此处自助邮件我。</p>
        </div>
      </div>
    </div>
  );
}

function Thanks() {
  return (
    <div className={styles.thanks}>
      <div className={styles.line}></div>
      <div className={styles.content}>
        <h3>感谢他们</h3>
        <p>
          <a target="_blank" href="https://www.shiyanlou.com/courses/599" className={styles["highlight-name"]}>
            实验楼：高德API+Python解决租房问题、
          </a>
          <a href="https://github.com/CodeForCSharp" className={styles["highlight-name"]} target="_blank">
            CodeForCSharp
          </a>
          、
          <a href="https://github.com/xiaoshayu123" className={styles["highlight-name"]} target="_blank">
            xiaoshayu123
          </a>
          、
          <a href="https://github.com/Erane" className={styles["highlight-name"]} target="_blank">
            Erane
          </a>
          、
          <a href="https://github.com/piratf" target="_blank">
            piratf
          </a>
        </p>
        <ul>
          <li>
            <img src="/images/microsoft.png" alt="微软" />
          </li>
          <li>
            <a href="https://house2048.cn" target="_blank">
              <img src="/images/kala-2024-300px.png" alt="深圳考拉弟弟" />
            </a>
          </li>
          <li>
            <a href="https://iinti.cn/zh-cn/" target="_blank">
              <img src="https://iinti.cn/images/logos/logo.png" alt="因体科技" />
            </a>
          </li>
        </ul>
      </div>
    </div>
  );
}

function Contact() {
  return (
    <div className={styles.contact}>
      <div>
        <p>有更好的房源平台推荐? 想吐槽一下网站内容? 可以通过以下方式联系我啦.</p>
        <div className={styles.ways}>
          <div>
            <span>知乎:</span>
            <a href="https://www.zhihu.com/people/codelover" className={styles["highlight-name"]} target="_blank">
              李国宝
            </a>
          </div>
          <div>
            <span>GitHub:</span>
            <a href="https://github.com/liguobao/HouseSearch" className={styles["highlight-name"]} target="_blank">
              liguobao/HouseSearch
            </a>
          </div>
          <div>
            <span>邮件:</span>
            <em>codelover@qq.com</em>
          </div>
        </div>
        <div className={styles.ewm}>
          <img src="./../images/ewm.jpg" />
          <span>( 欢迎关注【人生删除指南】微信公众号获取租房技巧/体验地图搜租房小程序/房源精选. )</span>
        </div>
      </div>
    </div>
  );
}

function Footer() {
  const year = 2024;
  return (
    <footer>
      <div>
        <div>
          Copyright 2016 - {year} www.woyaozufang.live. All Rights Reserved
          <a href="https://beian.miit.gov.cn/#/Integrated/index" className={styles["highlight-name"]} target="_blank">
            粤ICP备20003432号-1
          </a>
          <a href="/" className={styles["highlight-name"]}>
            地图搜租房
          </a>
        </div>
      </div>
    </footer>
  );
}

export default Home;

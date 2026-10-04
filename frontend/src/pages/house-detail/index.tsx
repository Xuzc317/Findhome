import BaseLayout from "@/components/layout";
import styles from "./styles.module.css";
import { useEffect, useState } from "react";
import { housesService } from "@/services";
import { useParams } from "react-router-dom";
import { Carousel, message, Spin, Tag } from "antd";
import { LoadingOutlined } from "@ant-design/icons";

export default function HouseDetail() {
  const params = useParams();
  const [house, setHouse] = useState<HouseDetail>();

  useEffect(() => {
    if (!params.id) return;
    housesService
      .getHouseDetail(params.id)
      .then((res) => {
        setHouse(res);
      })
      .catch((err) => {
        message.error(err.message);
      });
  }, [params]);
  if (!house) return <LoadingPage />;
  return (
    <BaseLayout>
      <a className={styles.title} href={house.onlineURL} target="__black">
        {house.title}
      </a>
      <div className={styles.container}>
        <Carousel className={styles.carousel} arrows>
          {house.pictures.map((img) => (
            <div className={styles.imageItem}>
              <img src={img} />
            </div>
          ))}
        </Carousel>
        <div className={styles.content}>
          <div className="flex items-center mt-4">
            <Tag color="orange">{house.displayRentType}</Tag>
            <Tag color="magenta">{house.displaySource}</Tag>
            <div className={styles.price}>
              <span>{house.price == -1 ? "未知" : house.price}</span>/月
            </div>
          </div>
          <div className="mt-4">所在城市：{house.city}</div>
          {/* 平台时间：发布时间；仅有维护时间时标注"(维护)"；都没有则显示"未知"，
              不拿采集时间冒充发布时间 */}
          <div className="mt-4">
            发布时间：{house.timeText || "未知"}
          </div>
          <div className="mt-4 text-gray-600 whitespace-pre-wrap">{getDomText(house.text)}</div>
          <a href={house.onlineURL} target="__black" className="mt-4 text-xl">
            查看来源
          </a>
        </div>
      </div>
    </BaseLayout>
  );
}

function LoadingPage() {
  return (
    <BaseLayout>
      <Spin indicator={<LoadingOutlined spin />} size="large"></Spin>
    </BaseLayout>
  );
}

function getDomText(html: string) {
  const div = document.createElement("div");
  div.innerHTML = html;
  return div.textContent;
}

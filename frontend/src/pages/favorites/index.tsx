import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Segmented,
  Space,
  Spin,
  Tag,
  message,
} from "antd";
import { Helmet } from "react-helmet";
import BaseLayout from "@/components/layout";
import { HouseMark, markService } from "@/services/mark";

const SOURCE_LABEL: Record<string, string> = {
  xianyu: "闲鱼",
  xiaohongshu: "小红书",
  douban: "豆瓣",
  beike: "贝壳",
};

const LAYOUT_LABEL: Record<string, string> = {
  studio: "单间",
  "1b1l": "1房1厅",
  "2b1l": "2房1厅",
  "3b1l": "3房1厅",
  "4b+": "4房及以上",
};

type Filter = "favorite" | "contacted" | "noted" | "hidden" | "all";

export default function FavoritesPage() {
  const [filter, setFilter] = useState<Filter>("favorite");
  const [items, setItems] = useState<HouseMark[]>([]);
  const [loading, setLoading] = useState(true);

  const load = (f: Filter) => {
    setLoading(true);
    markService
      .list(f)
      .then((res) => setItems(res.items))
      .catch(() => message.error("读取失败"))
      .finally(() => setLoading(false));
  };

  useEffect(() => load(filter), [filter]);

  const removeMark = async (m: HouseMark) => {
    try {
      await markService.update(m.houseId, {
        favorite: false,
        contacted: false,
        hidden: false,
        note: "",
      });
      setItems((prev) => prev.filter((x) => x.houseId !== m.houseId));
      message.success("已移出");
    } catch {
      message.error("操作失败");
    }
  };

  return (
    <BaseLayout>
      <Helmet>
        <title>我的收藏与记录 · Findhome</title>
      </Helmet>

      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "16px 16px 60px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h2 style={{ margin: 0, fontSize: 20 }}>我的收藏与记录</h2>
          <Button size="small" onClick={() => load(filter)}>
            刷新
          </Button>
        </div>

        <Alert
          style={{ marginTop: 12 }}
          type="info"
          showIcon
          message="这些是你自己的数据，与平台采集分开保存"
          description="房源信息会被重新采集覆盖，但你的收藏、联系记录和备注独立存放在本地数据库，不会随之丢失。"
        />

        <div style={{ marginTop: 16 }}>
          <Segmented
            value={filter}
            onChange={(v) => setFilter(v as Filter)}
            options={[
              { label: "⭐ 收藏", value: "favorite" },
              { label: "☎ 已联系", value: "contacted" },
              { label: "📝 有备注", value: "noted" },
              { label: "🚫 不感兴趣", value: "hidden" },
              { label: "全部", value: "all" },
            ]}
          />
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: 60 }}>
            <Spin />
          </div>
        ) : items.length === 0 ? (
          <Empty
            style={{ padding: "60px 0" }}
            description={
              filter === "favorite"
                ? "还没有收藏。在结果页点卡片上的「☆ 收藏」就会出现在这里"
                : "暂无记录"
            }
          />
        ) : (
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            {items.map((m) => {
              const h = m.house;
              const pic = h?.pictures?.[0];
              return (
                <Col xs={24} md={12} lg={8} key={m.houseId}>
                  <Card
                    size="small"
                    hoverable
                    onClick={() => h && window.open(`/houses/${h.id}`)}
                    cover={
                      pic ? (
                        <img
                          src={pic}
                          alt=""
                          referrerPolicy="no-referrer"
                          style={{ height: 160, objectFit: "cover" }}
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = "none";
                          }}
                        />
                      ) : (
                        <div
                          style={{
                            height: 160,
                            background: "#f5f5f5",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            color: "#bfbfbf",
                            fontSize: 13,
                          }}
                        >
                          无图片
                        </div>
                      )
                    }
                  >
                    <div style={{ fontWeight: 600, fontSize: 13, lineHeight: "19px", minHeight: 38 }}>
                      {h?.title || "(房源已不在库中)"}
                    </div>
                    <Space size={6} wrap style={{ marginTop: 8 }}>
                      {h?.price != null && <Tag color="orange">￥{h.price}</Tag>}
                      {h?.layoutKey && <Tag color="blue">{LAYOUT_LABEL[h.layoutKey] || h.layoutKey}</Tag>}
                      {h?.source && <Tag color="magenta">{SOURCE_LABEL[h.source] || h.source}</Tag>}
                      {m.favorite && <Tag color="gold">⭐ 收藏</Tag>}
                      {m.contacted && <Tag color="green">☎ 已联系</Tag>}
                      {m.hidden && <Tag>🚫 不感兴趣</Tag>}
                    </Space>
                    {m.note && (
                      <div
                        style={{
                          marginTop: 8,
                          fontSize: 12,
                          color: "#8c8c8c",
                          background: "#fffbe6",
                          border: "1px solid #ffe58f",
                          borderRadius: 6,
                          padding: "4px 8px",
                        }}
                      >
                        📝 {m.note}
                      </div>
                    )}
                    <div style={{ marginTop: 10, display: "flex", justifyContent: "space-between" }}>
                      {h?.sourceUrl ? (
                        <a
                          href={h.sourceUrl}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          style={{ fontSize: 12 }}
                        >
                          查看原帖 ↗
                        </a>
                      ) : (
                        <span />
                      )}
                      <Button
                        size="small"
                        danger
                        type="link"
                        onClick={(e) => {
                          e.stopPropagation();
                          removeMark(m);
                        }}
                      >
                        移出
                      </Button>
                    </div>
                  </Card>
                </Col>
              );
            })}
          </Row>
        )}
      </div>
    </BaseLayout>
  );
}

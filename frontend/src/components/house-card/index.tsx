import { Button, Input, Modal, Tag, Tooltip, message } from "antd";
import { useState } from "react";
import type { MatchedHouse } from "@/services/match";
import { HouseMark, markService } from "@/services/mark";

export const SOURCE_LABEL: Record<string, string> = {
  xianyu: "闲鱼",
  xiaohongshu: "小红书",
  douban: "豆瓣",
  beike: "贝壳",
};

/** 电梯：事实与推断分开，未标注 ≠ 没有 */
function ElevatorTag({ item }: { item: MatchedHouse }) {
  if (item.elevator === true) {
    return (
      <Tooltip title={`原文依据：${item.elevator_evidence || "—"}`}>
        <Tag color="green" style={{ margin: 0, fontSize: 11 }}>✅ 电梯</Tag>
      </Tooltip>
    );
  }
  if (item.elevator === false) {
    return (
      <Tooltip title={`原文依据：${item.elevator_evidence || "—"}`}>
        <Tag color="red" style={{ margin: 0, fontSize: 11 }}>❌ 无电梯</Tag>
      </Tooltip>
    );
  }
  return (
    <Tooltip title={item.elevator_hint || "平台没写电梯，需自行确认（未标注不等于没有）"}>
      <Tag style={{ margin: 0, fontSize: 11 }}>❓ 电梯未标注</Tag>
    </Tooltip>
  );
}

function KindTag({ item }: { item: MatchedHouse }) {
  if (item.listing_kind === "sublet") {
    return (
      <Tooltip title="转租：原租客因工作/离开等原因转让合同。图片与价格通常真实，中介很少做这类。">
        <Tag color="gold" style={{ margin: 0, fontSize: 11 }}>🔑 转租</Tag>
      </Tooltip>
    );
  }
  if (item.listing_kind === "direct") {
    return (
      <Tooltip title="标题写明房东直租/无中介费（注意：中介也会这么写，需结合发布者身份判断）">
        <Tag color="cyan" style={{ margin: 0, fontSize: 11 }}>直接房东</Tag>
      </Tooltip>
    );
  }
  return null;
}

function PosterTag({ item }: { item: MatchedHouse }) {
  if (item.poster_type === "agency") {
    return (
      <Tooltip
        title={`该发布者在租 ${item.seller_listings} 套，疑似中介/机构。\n实测这类房源图片多为宣传图，建议先要实拍视频。`}
      >
        <Tag color="volcano" style={{ margin: 0, fontSize: 11 }}>
          🏢 疑似中介 · {item.seller_listings}套
        </Tag>
      </Tooltip>
    );
  }
  if (item.poster_type === "individual") {
    return (
      <Tooltip title="该发布者只挂了这一套，更像个人房东">
        <Tag color="green" style={{ margin: 0, fontSize: 11 }}>👤 个人房东</Tag>
      </Tooltip>
    );
  }
  return null;
}

export function HouseCard({
  item,
  showStation = true,
  mark,
  onMarkChange,
}: {
  item: MatchedHouse;
  showStation?: boolean;
  mark?: Partial<HouseMark>;
  onMarkChange?: (next: HouseMark | null) => void;
}) {
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteDraft, setNoteDraft] = useState(mark?.note || "");
  const [busy, setBusy] = useState(false);

  const favorite = !!mark?.favorite;
  const contacted = !!mark?.contacted;
  const hidden = !!mark?.hidden;

  const toggle = async (patch: Record<string, unknown>) => {
    setBusy(true);
    try {
      const next = await markService.update(item.house_id, patch as any);
      onMarkChange?.(next);
    } catch {
      message.error("保存标记失败");
    } finally {
      setBusy(false);
    }
  };
  const walkText =
    item.walk_minutes != null
      ? `🚇 步行 ${item.walk_minutes} 分钟 · ${item.walk_m}m`
      : item.walk_status === "位置待确认"
        ? "📍 仅知在站附近"
        : "步行未计算";

  return (
    <div
      style={{
        marginBottom: 20,
        borderRadius: 12,
        border: "1px solid #f0f0f0",
        overflow: "hidden",
        cursor: "pointer",
        background: "#fff",
        transition: "all .18s",
      }}
      onClick={() => window.open(`/houses/${item.house_id}`)}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = "0 6px 20px rgba(0,0,0,.08)";
        e.currentTarget.style.transform = "translateY(-2px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = "none";
        e.currentTarget.style.transform = "none";
      }}
    >
      <div style={{ position: "relative", background: "#f5f5f5", height: 180 }}>
        {item.picture ? (
          <img
            src={item.picture}
            alt={item.title}
            loading="lazy"
            referrerPolicy="no-referrer"
            style={{ width: "100%", height: 180, objectFit: "cover", display: "block" }}
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          <div
            style={{
              height: 180,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#bfbfbf",
              fontSize: 13,
            }}
          >
            该房源未提供图片
          </div>
        )}
        <div
          style={{
            position: "absolute",
            left: 8,
            bottom: 8,
            padding: "3px 9px",
            fontSize: 12,
            fontWeight: 600,
            color: "#fff",
            background: "rgba(0,163,202,.92)",
            borderRadius: 10,
          }}
        >
          {walkText}
        </div>
        {item.price != null && (
          <div
            style={{
              position: "absolute",
              right: 8,
              top: 8,
              padding: "3px 10px",
              fontSize: 15,
              fontWeight: 700,
              color: "#fff",
              background: "rgba(250,84,28,.92)",
              borderRadius: 10,
            }}
          >
            ￥{item.price}
          </div>
        )}
      </div>

      <div style={{ padding: "10px 12px 12px" }}>
        <div
          style={{
            fontWeight: 600,
            fontSize: 14,
            lineHeight: "20px",
            color: "#262626",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {item.title}
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
          <Tag color="blue" style={{ margin: 0, fontSize: 11 }}>{item.layout_label}</Tag>
          <KindTag item={item} />
          <ElevatorTag item={item} />
          <Tooltip title={item.newness_signals?.join("、") || "无明显新旧信号"}>
            <Tag
              color={item.newness_score >= 70 ? "cyan" : "default"}
              style={{ margin: 0, fontSize: 11 }}
            >
              新旧 {item.newness_score}
            </Tag>
          </Tooltip>
        </div>

        {showStation && (
          <div style={{ marginTop: 8, fontSize: 12, color: "#595959" }}>
            🚉 {item.nearest_station}
            {item.nearest_station_lines?.length
              ? `（${item.nearest_station_lines.join("/")}）`
              : ""}
            {item.straight_m ? ` · 直线 ${item.straight_m}m` : ""}
          </div>
        )}
        {(item.community || item.district) && (
          <div style={{ marginTop: 4, fontSize: 12, color: "#8c8c8c" }}>
            📍 {item.district || ""} {item.community || ""}
          </div>
        )}

        {item.caveats?.length > 0 && (
          <div style={{ marginTop: 6, fontSize: 11, color: "#fa8c16" }}>
            ⚠️ {item.caveats[0]}
          </div>
        )}

        {/* 操作按键：收藏 / 已联系 / 不感兴趣 / 备注
            这些是用户自己的数据，落库保存，采集覆盖房源时不会丢 */}
        <div
          style={{ marginTop: 10, display: "flex", gap: 6, flexWrap: "wrap" }}
          onClick={(e) => e.stopPropagation()}
        >
          <Button
            size="small"
            type={favorite ? "primary" : "default"}
            danger={favorite}
            loading={busy}
            onClick={() => toggle({ favorite: !favorite })}
          >
            {favorite ? "★ 已收藏" : "☆ 收藏"}
          </Button>
          <Button
            size="small"
            type={contacted ? "primary" : "default"}
            loading={busy}
            onClick={() => toggle({ contacted: !contacted })}
          >
            {contacted ? "✔ 已联系" : "☎ 已联系"}
          </Button>
          <Button
            size="small"
            type={hidden ? "primary" : "default"}
            loading={busy}
            onClick={() => toggle({ hidden: !hidden })}
          >
            {hidden ? "🚫 已排除" : "🚫 不感兴趣"}
          </Button>
          <Button
            size="small"
            onClick={() => {
              setNoteDraft(mark?.note || "");
              setNoteOpen(true);
            }}
          >
            {mark?.note ? "📝 备注*" : "📝 备注"}
          </Button>
        </div>

        {mark?.note && (
          <div
            style={{
              marginTop: 6,
              fontSize: 12,
              color: "#8c8c8c",
              background: "#fffbe6",
              border: "1px solid #ffe58f",
              borderRadius: 6,
              padding: "4px 8px",
            }}
          >
            📝 {mark.note}
          </div>
        )}

        <div
          style={{
            marginTop: 10,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
            <Tag color="magenta" style={{ margin: 0, fontSize: 11 }}>
              {SOURCE_LABEL[item.source] || item.source}
            </Tag>
            <PosterTag item={item} />
          </span>
          <a
            href={item.source_url}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            style={{ fontSize: 12 }}
          >
            查看原帖 ↗
          </a>
        </div>
      </div>

      <Modal
        title="我的备注"
        open={noteOpen}
        onCancel={() => setNoteOpen(false)}
        onOk={async () => {
          await toggle({ note: noteDraft });
          setNoteOpen(false);
        }}
        okText="保存"
        cancelText="取消"
      >
        <Input.TextArea
          rows={4}
          maxLength={500}
          showCount
          placeholder="例如：周六下午看房、问清楚电梯和物业费、房东说可以短租"
          value={noteDraft}
          onChange={(e) => setNoteDraft(e.target.value)}
        />
      </Modal>
    </div>
  );
}

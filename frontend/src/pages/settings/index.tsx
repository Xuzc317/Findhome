import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Row,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import { Helmet } from "react-helmet";
import BaseLayout from "@/components/layout";
import { API_BASE_URL } from "@/constant";
import axios from "axios";

const { Paragraph, Text } = Typography;

interface IntegrationStatus {
  amap: {
    jsKey: string;
    jsSecurityCode: string;
    jsConfigured: boolean;
    webServiceConfigured: boolean;
    webServiceMasked: string;
    available: boolean;
    note: string;
  };
  llm: {
    provider: string;
    deepseekConfigured: boolean;
    doubaoConfigured: boolean;
    available: boolean;
    thinking: string;
    note: string;
  };
  sources: {
    key: string;
    name: string;
    access: string;
    note: string;
    enabled: boolean;
    cookieConfigured: boolean;
  }[];
  cookieImport: {
    supported: string[];
    tools: Record<string, string>;
    note: string;
  };
}

function StatusTag({ ok, okText, failText }: { ok: boolean; okText: string; failText: string }) {
  return <Tag color={ok ? "green" : "default"}>{ok ? okText : failText}</Tag>;
}

export default function SettingsPage() {
  const [data, setData] = useState<IntegrationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    axios
      .get(`${API_BASE_URL}/settings`)
      .then((res) => setData(res.data?.data))
      .catch((e) => setError(e?.message || "读取配置失败"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  if (loading) {
    return (
      <BaseLayout>
        <div style={{ textAlign: "center", padding: 80 }}>
          <Spin />
        </div>
      </BaseLayout>
    );
  }

  return (
    <BaseLayout>
      <Helmet>
        <title>配置与集成 · Findhome</title>
      </Helmet>

      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "16px 16px 60px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <h2 style={{ margin: 0, fontSize: 20 }}>配置与集成</h2>
          <Button size="small" onClick={load}>刷新</Button>
        </div>

        {error && <Alert type="error" showIcon style={{ marginTop: 16 }} message={error} />}

        <Alert
          style={{ marginTop: 16 }}
          type="info"
          showIcon
          message="这里只显示「是否已配置」与脱敏后的状态"
          description="服务端密钥（高德 Web 服务 Key、大模型 Key）与各平台 Cookie 不会下发到浏览器，只返回是否配置与掩码。前端地图需要的高德 JS Key 例外——那正是它本来的用法。"
        />

        {/* 高德 */}
        <Card title="高德地图" style={{ marginTop: 16 }}>
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="Web 服务 Key（后端用）">
              <Space>
                <StatusTag
                  ok={!!data?.amap.webServiceConfigured}
                  okText="已配置"
                  failText="未配置"
                />
                <Text type="secondary">{data?.amap.webServiceMasked || "—"}</Text>
                <Text type="secondary">地理编码 / POI / 真实步行路径 / 地铁站校准</Text>
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="Web 端 JS Key（前端地图用）">
              <Space>
                <StatusTag ok={!!data?.amap.jsConfigured} okText="已配置" failText="未配置" />
                <Text type="secondary">由后端运行时下发，不打包进静态资源</Text>
              </Space>
            </Descriptions.Item>
            <Descriptions.Item label="可用性">
              <StatusTag
                ok={!!data?.amap.available}
                okText="可计算真实步行距离"
                failText="缺少 Web 服务 Key"
              />
            </Descriptions.Item>
          </Descriptions>
          <Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0, fontSize: 12 }}>
            {data?.amap.note}
          </Paragraph>
        </Card>

        {/* 大模型 */}
        <Card title="大模型（用于从文字/图片推断房源位置）" style={{ marginTop: 16 }}>
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="当前供应商">
              <Tag color="blue">{data?.llm.provider}</Tag>
              <Text type="secondary">auto 时两家互为兜底</Text>
            </Descriptions.Item>
            <Descriptions.Item label="DeepSeek">
              <StatusTag
                ok={!!data?.llm.deepseekConfigured}
                okText="已配置"
                failText="未配置"
              />
            </Descriptions.Item>
            <Descriptions.Item label="豆包（火山方舟）">
              <StatusTag
                ok={!!data?.llm.doubaoConfigured}
                okText="已配置"
                failText="未配置"
              />
            </Descriptions.Item>
            <Descriptions.Item label="思考模式">
              <Tag>{data?.llm.thinking}</Tag>
              <Text type="secondary">抽取任务关闭思考以提速降本</Text>
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* 数据源 */}
        <Card title="数据源与登录态" style={{ marginTop: 16 }}>
          <Table
            size="small"
            pagination={false}
            rowKey="key"
            dataSource={data?.sources || []}
            columns={[
              { title: "平台", dataIndex: "name", width: 110 },
              {
                title: "启用",
                dataIndex: "enabled",
                width: 90,
                render: (v: boolean) =>
                  v ? <Tag color="green">启用</Tag> : <Tag>已放弃</Tag>,
              },
              {
                title: "登录态",
                dataIndex: "cookieConfigured",
                width: 110,
                render: (v: boolean, r) =>
                  r.access === "disabled" ? (
                    <Text type="secondary">—</Text>
                  ) : (
                    <StatusTag ok={v} okText="已有" failText="未配置" />
                  ),
              },
              {
                title: "接入方式",
                dataIndex: "access",
                width: 110,
                render: (v: string) =>
                  ({
                    browser: <Tag color="purple">浏览器</Tag>,
                    http: <Tag color="blue">直连接口</Tag>,
                    disabled: <Tag>已放弃</Tag>,
                  })[v] || <Tag>{v}</Tag>,
              },
              { title: "说明", dataIndex: "note" },
            ]}
          />
        </Card>

        {/* 登录工具 */}
        <Card title="登录与凭据" style={{ marginTop: 16 }}>
          <Paragraph style={{ marginBottom: 8 }}>
            <Text strong>安全约定：</Text>
            {data?.cookieImport.note}
          </Paragraph>
          <Row gutter={[16, 12]}>
            {Object.entries(data?.cookieImport.tools || {}).map(([k, v]) => (
              <Col xs={24} md={8} key={k}>
                <Card size="small" style={{ background: "#fafafa" }}>
                  <Text code style={{ fontSize: 12 }}>{v}</Text>
                </Card>
              </Col>
            ))}
          </Row>
          <Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0, fontSize: 12 }}>
            支持平台：{data?.cookieImport.supported.join("、")}。
            只接受本人浏览器登录后的会话，脚本不读取输入、不处理密码、不绕过验证码。
          </Paragraph>
        </Card>
      </div>
    </BaseLayout>
  );
}

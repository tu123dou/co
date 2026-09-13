import { Alert, Drawer, Table, Tabs, Tag } from "antd";
import type { WorkbenchCatalog } from "../../../../models/workbench";

/** 智能问数使用的数据范围与指标口径说明。 */
export default function DataCatalogDrawer({ open, catalog, onClose }: { open: boolean; catalog: WorkbenchCatalog | null; onClose: () => void }) {
  return <Drawer title="数据与指标" open={open} onClose={onClose} width={600}>
    {catalog && <>
      <Alert type="info" message="算力基础设施与服务 · 经营数据"
        description={`覆盖 ${catalog.dataset.start_date} 至 ${catalog.dataset.cutoff_date}，固定种子生成，所有金额采用不含税管理口径。`}
        showIcon />
      <Tabs items={[
        { key: "metrics", label: "指标口径", children: <div className="metric-list">
          {Object.entries(catalog.metrics).map(([key, metric]) => <div key={key}>
            <h3>{metric.name}<Tag>{metric.unit}</Tag></h3>
            <p>{metric.definition}</p><small>{key} · v1</small>
          </div>)}
        </div> },
        { key: "data", label: "数据范围", children: <>
          <h3>经营单元</h3><div className="tag-wrap">{catalog.values.org_unit.map((value: string) => <Tag key={value}>{value}</Tag>)}</div>
          <h3>产品线</h3><div className="tag-wrap">{catalog.values.product_line.map((value: string) => <Tag key={value}>{value}</Tag>)}</div>
          <h3>数据记录</h3>
          <Table rowKey="table" size="small" pagination={false}
            columns={[
              { title: "数据表", dataIndex: "table" },
              { title: "数据表描述", dataIndex: "description" },
              { title: "记录数", dataIndex: "count", align: "right" },
            ]}
            dataSource={catalog.data_tables || []} scroll={{ x: 620 }} />
        </> },
      ]} />
    </>}
  </Drawer>;
}

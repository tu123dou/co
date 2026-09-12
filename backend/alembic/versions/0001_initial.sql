-- 第一版数据库结构快照：创建 app 与 analytics 模式及其基础表和约束。
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE SCHEMA IF NOT EXISTS app;


CREATE TABLE analytics.industries (
	id SERIAL NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
)

;


CREATE TABLE analytics.org_units (
	id SERIAL NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	region VARCHAR(30) NOT NULL, 
	city VARCHAR(30) NOT NULL, 
	parent_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	FOREIGN KEY(parent_id) REFERENCES analytics.org_units (id)
)

;


CREATE TABLE analytics.product_lines (
	id SERIAL NOT NULL, 
	name VARCHAR(60) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
)

;


CREATE TABLE app.dataset_versions (
	id SERIAL NOT NULL, 
	version VARCHAR(80) NOT NULL, 
	seed INTEGER NOT NULL, 
	start_date DATE NOT NULL, 
	cutoff_date DATE NOT NULL, 
	counts JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (version)
)

;


CREATE TABLE app.metric_definitions (
	id SERIAL NOT NULL, 
	code VARCHAR(80) NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	version INTEGER NOT NULL, 
	definition JSONB NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code, version)
)

;


CREATE TABLE app.users (
	id SERIAL NOT NULL, 
	username VARCHAR(80) NOT NULL, 
	password_hash TEXT NOT NULL, 
	display_name VARCHAR(80) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	active BOOLEAN DEFAULT 'true' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username)
)

;


CREATE TABLE analytics.customers (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	industry_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	FOREIGN KEY(industry_id) REFERENCES analytics.industries (id)
)

;


CREATE TABLE analytics.monthly_targets (
	id SERIAL NOT NULL, 
	month DATE NOT NULL, 
	org_unit_id INTEGER NOT NULL, 
	product_line_id INTEGER NOT NULL, 
	revenue_target NUMERIC(18, 2) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (month, org_unit_id, product_line_id), 
	CHECK (revenue_target > 0), 
	FOREIGN KEY(org_unit_id) REFERENCES analytics.org_units (id), 
	FOREIGN KEY(product_line_id) REFERENCES analytics.product_lines (id)
)

;


CREATE TABLE analytics.products (
	id SERIAL NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	product_line_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_line_id) REFERENCES analytics.product_lines (id)
)

;


CREATE TABLE analytics.salespeople (
	id SERIAL NOT NULL, 
	name VARCHAR(60) NOT NULL, 
	org_unit_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_unit_id) REFERENCES analytics.org_units (id)
)

;


CREATE TABLE app.conversations (
	id VARCHAR(36) NOT NULL, 
	user_id INTEGER NOT NULL, 
	title VARCHAR(100) NOT NULL, 
	pinned BOOLEAN DEFAULT 'false' NOT NULL, 
	context JSONB DEFAULT '{}' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES app.users (id)
)

;

CREATE INDEX ix_conversations_user_id_updated_at ON app.conversations (user_id, updated_at);


CREATE TABLE app.favorite_questions (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	question VARCHAR(1000) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id, question), 
	FOREIGN KEY(user_id) REFERENCES app.users (id)
)

;


CREATE TABLE analytics.contracts (
	id SERIAL NOT NULL, 
	number VARCHAR(30) NOT NULL, 
	customer_id INTEGER NOT NULL, 
	org_unit_id INTEGER NOT NULL, 
	salesperson_id INTEGER NOT NULL, 
	signed_date DATE NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (number), 
	FOREIGN KEY(customer_id) REFERENCES analytics.customers (id), 
	FOREIGN KEY(org_unit_id) REFERENCES analytics.org_units (id), 
	FOREIGN KEY(salesperson_id) REFERENCES analytics.salespeople (id)
)

;

CREATE INDEX ix_contracts_customer_id ON analytics.contracts (customer_id);

CREATE INDEX ix_contracts_signed_date ON analytics.contracts (signed_date);


CREATE TABLE app.messages (
	id VARCHAR(36) NOT NULL, 
	conversation_id VARCHAR(36) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	content TEXT NOT NULL, 
	result JSONB, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES app.conversations (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_messages_conversation_id_created_at ON app.messages (conversation_id, created_at);


CREATE TABLE analytics.contract_items (
	id SERIAL NOT NULL, 
	contract_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	amount_ex_tax NUMERIC(18, 2) NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount_ex_tax >= 0), 
	FOREIGN KEY(contract_id) REFERENCES analytics.contracts (id), 
	FOREIGN KEY(product_id) REFERENCES analytics.products (id)
)

;

CREATE INDEX ix_contract_items_contract_id ON analytics.contract_items (contract_id);


CREATE TABLE analytics.payment_entries (
	id SERIAL NOT NULL, 
	contract_id INTEGER NOT NULL, 
	payment_date DATE NOT NULL, 
	amount_ex_tax NUMERIC(18, 2) NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount_ex_tax >= 0), 
	FOREIGN KEY(contract_id) REFERENCES analytics.contracts (id)
)

;

CREATE INDEX ix_payment_entries_payment_date_contract_id ON analytics.payment_entries (payment_date, contract_id);


CREATE TABLE app.feedbacks (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	message_id VARCHAR(36) NOT NULL, 
	comment TEXT NOT NULL, 
	status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES app.users (id), 
	FOREIGN KEY(message_id) REFERENCES app.messages (id) ON DELETE CASCADE
)

;


CREATE TABLE app.query_runs (
	id VARCHAR(36) NOT NULL, 
	message_id VARCHAR(36) NOT NULL, 
	plan JSONB, 
	sql TEXT, 
	parameters JSONB, 
	status VARCHAR(30) NOT NULL, 
	error_code VARCHAR(50), 
	duration_ms INTEGER, 
	model VARCHAR(100), 
	usage JSONB, 
	dataset_version VARCHAR(80), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(message_id) REFERENCES app.messages (id) ON DELETE CASCADE
)

;


CREATE TABLE analytics.cost_entries (
	id SERIAL NOT NULL, 
	contract_item_id INTEGER NOT NULL, 
	cost_date DATE NOT NULL, 
	amount_ex_tax NUMERIC(18, 2) NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount_ex_tax >= 0), 
	FOREIGN KEY(contract_item_id) REFERENCES analytics.contract_items (id)
)

;

CREATE INDEX ix_cost_entries_cost_date_contract_item_id ON analytics.cost_entries (cost_date, contract_item_id);


CREATE TABLE analytics.revenue_entries (
	id SERIAL NOT NULL, 
	contract_item_id INTEGER NOT NULL, 
	recognition_date DATE NOT NULL, 
	amount_ex_tax NUMERIC(18, 2) NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (amount_ex_tax >= 0), 
	FOREIGN KEY(contract_item_id) REFERENCES analytics.contract_items (id)
)

;

CREATE INDEX ix_revenue_entries_recognition_date_contract_item_id ON analytics.revenue_entries (recognition_date, contract_item_id);

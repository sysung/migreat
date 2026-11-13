# Add a PostgreSQL column with migreat

Start with ten orders in a disposable PostgreSQL database. Use an Open Data Contract Standard (ODCS) file to declare a new nullable column, then review and apply the SQL that migreat generates.

## 1. Write the contract

From the repository root, save this YAML as `orders.yaml`.

```yaml
apiVersion: v3.2.0
kind: DataContract
id: orders
version: 1.1.0
schema:
  - name: orders
    physicalName: public.orders
    physicalType: table
    properties:
      - name: id
        logicalType: integer
        physicalType: bigint
        required: true
      - name: amount_cents
        logicalType: integer
        physicalType: bigint
        required: false
```

`apiVersion` selects the ODCS version. `physicalName` identifies the PostgreSQL schema and table. List both the existing `id` and the new `amount_cents` because the contract describes the desired table. `logicalType` describes the kind of value and `physicalType` gives its PostgreSQL type. `required: false` makes `amount_cents` nullable.

## 2. Start and seed PostgreSQL

```sh
docker network create migreat-guide
docker run --rm -d --name migreat-guide-db --network migreat-guide \
  -p 127.0.0.1:55432:5432 -e POSTGRES_PASSWORD=demo postgres:17.12
```

Wait for the command below to report that PostgreSQL is accepting connections. Then seed the table.

```sh
docker exec migreat-guide-db pg_isready -h 127.0.0.1 -U postgres

docker exec -i migreat-guide-db psql -U postgres -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE public.orders (id bigint PRIMARY KEY);
INSERT INTO public.orders SELECT generate_series(1, 10);
SQL
```

## 3. Preview and apply

Choose one of the two paths below. Both use the same demo database. After the first apply, the other path will report `No changes.`

### Installed CLI

Follow the [Python setup](../README.md#run-locally) and run these commands with the virtual environment active.

```sh
export DATABASE_URL=postgresql://postgres:demo@127.0.0.1:55432/postgres
migreat plan orders.yaml
migreat apply orders.yaml
```

### Docker CLI

Use the database container name as the hostname and mount the contract read-only.

```sh
docker build -t migreat .
export DATABASE_URL=postgresql://postgres:demo@migreat-guide-db/postgres
docker run --rm --network migreat-guide -e DATABASE_URL \
  -v "$PWD/orders.yaml:/orders.yaml:ro" migreat plan /orders.yaml
docker run --rm -it --network migreat-guide -e DATABASE_URL \
  -v "$PWD/orders.yaml:/orders.yaml:ro" migreat apply /orders.yaml
```

The preview shows this SQL. Review it again at the apply prompt, then type `yes`.

```sql
ALTER TABLE "public"."orders" ADD COLUMN "amount_cents" bigint;
```

## 4. Check the rows

```sh
docker exec migreat-guide-db psql -U postgres -c \
  'SELECT count(*) AS orders, count(amount_cents) AS populated FROM public.orders;'
```

Expect `orders = 10` and `populated = 0`. Existing rows read `NULL` in the new column. A repeat plan reports `No changes.`

```sh
docker stop migreat-guide-db
docker network rm migreat-guide
unset DATABASE_URL
```

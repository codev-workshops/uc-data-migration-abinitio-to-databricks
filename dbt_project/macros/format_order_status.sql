/*
  format_order_status.sql
  Migrated from: an Ab Initio lookup/reformat that expands order status codes.

  Ab Initio expressions used inline lookup files / case logic to label codes.
  dbt equivalent: a Jinja macro returning a CASE expression.
  Usage: {{ format_order_status('order_status') }}
*/

{% macro format_order_status(column) %}
case {{ column }}
    when 'SHIPPED'    then 'Shipped'
    when 'DELIVERED'  then 'Delivered'
    when 'PROCESSING' then 'Processing'
    when 'CANCELLED'  then 'Cancelled'
    else 'Unknown'
end
{% endmacro %}

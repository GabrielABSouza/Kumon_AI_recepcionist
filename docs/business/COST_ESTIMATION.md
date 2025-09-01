# 💰 Cost Estimation - Kumon AI Receptionist on Google Cloud Run

## Overview

This document provides a detailed cost estimation for running the Kumon AI Receptionist system on Google Cloud Run with the cost-optimized configuration.

## Service Configuration

### 1. Kumon Assistant (Main Application)

- **Memory**: 2 GiB
- **CPU**: 2 vCPU
- **Min Instances**: 1
- **Max Instances**: 10
- **Concurrency**: 80 requests per instance

### 2. Evolution API (WhatsApp Integration)

- **Memory**: 1 GiB
- **CPU**: 1 vCPU
- **Min Instances**: 1
- **Max Instances**: 5
- **Concurrency**: 80 requests per instance

### 3. Qdrant Database (Vector Storage)

- **Memory**: 1 GiB
- **CPU**: 1 vCPU
- **Min Instances**: 1
- **Max Instances**: 3
- **Concurrency**: 80 requests per instance

## Cost Breakdown (Monthly Estimates)

### Base Costs (Always-On Services)

Since we're using minimum instances of 1 for each service:

| Service             | Memory | CPU    | Monthly Cost\*    |
| ------------------- | ------ | ------ | ----------------- |
| Kumon Assistant     | 2 GiB  | 2 vCPU | ~$35-45/month     |
| Evolution API       | 1 GiB  | 1 vCPU | ~$18-25/month     |
| Qdrant Database     | 1 GiB  | 1 vCPU | ~$18-25/month     |
| **Total Base Cost** |        |        | **~$71-95/month** |

\*Based on Google Cloud Run pricing as of 2024

### Additional Costs (Usage-Based)

#### Request Costs

- **Price**: $0.40 per 1 million requests
- **Estimated**: 50,000 requests/month
- **Monthly Cost**: ~$0.02/month

#### Data Transfer

- **Egress**: $0.12 per GB after 1GB free
- **Estimated**: 5GB/month
- **Monthly Cost**: ~$0.48/month

#### Google Secret Manager

- **Price**: $0.06 per 10,000 operations
- **Estimated**: 1,000 operations/month
- **Monthly Cost**: ~$0.01/month

### OpenAI API Costs

- **GPT-4**: $0.03 per 1K tokens (input) + $0.06 per 1K tokens (output)
- **Estimated**: 500 conversations/month, 2K tokens per conversation
- **Monthly Cost**: ~$45-90/month

## Total Monthly Cost Estimate

| Component                 | Cost Range   |
| ------------------------- | ------------ |
| Google Cloud Run Services | $71-95       |
| Request/Transfer Costs    | $0.51        |
| OpenAI API                | $45-90       |
| **Total Monthly Cost**    | **$116-186** |

## Cost Optimization Tips

### 1. Resource Optimization

- **Monitor actual usage** and adjust CPU/memory allocation
- **Set appropriate scaling limits** to prevent unexpected costs
- **Use minimum instances strategically** - consider 0 min instances for lower traffic

### 2. Request Optimization

- **Implement caching** to reduce redundant API calls
- **Batch operations** where possible
- **Optimize conversation flows** to reduce token usage

### 3. Traffic Management

- **Implement rate limiting** to prevent abuse
- **Use Cloud Load Balancer** for better traffic distribution
- **Monitor and alert** on unusual traffic patterns

### 4. Development/Testing

- **Use separate environments** with lower resource allocation
- **Implement proper testing** to avoid production issues
- **Use Cloud Run's free tier** for development

## Cost Monitoring Setup

### 1. Budget Alerts

```bash
# Set up budget alerts
gcloud billing budgets create \
  --billing-account=YOUR_BILLING_ACCOUNT \
  --display-name="Kumon AI Receptionist" \
  --budget-amount=200 \
  --threshold-rule=percent=80 \
  --threshold-rule=percent=100
```

### 2. Resource Monitoring

- **Cloud Monitoring**: Track CPU, memory, and request metrics
- **Logging**: Monitor for errors and unusual patterns
- **Cost Analysis**: Regular review of Cloud Billing reports

## Scaling Scenarios

### Low Traffic (< 1000 messages/month)

- **Estimated Cost**: $120-140/month
- **Recommendation**: Consider 0 min instances

### Medium Traffic (1000-10000 messages/month)

- **Estimated Cost**: $150-200/month
- **Current Configuration**: Optimal

### High Traffic (> 10000 messages/month)

- **Estimated Cost**: $200-350/month
- **Recommendation**: Consider dedicated instances or GKE

## Comparison with Managed Services

### Qdrant Cloud Alternative

- **Managed Qdrant**: ~$25/month for 1GB cluster
- **Self-managed**: ~$18-25/month
- **Savings**: ~$0-7/month (plus operational overhead)

### Evolution API Managed Alternative

- **Managed WhatsApp API**: $50-200/month
- **Self-managed**: ~$18-25/month
- **Savings**: ~$25-175/month

## Recommendations

### For Budget-Conscious Setup

1. **Start with 0 min instances** for development
2. **Monitor usage patterns** for 30 days
3. **Adjust resources** based on actual usage
4. **Set up billing alerts** at $150/month

### For Production Setup

1. **Use current configuration** for reliability
2. **Implement comprehensive monitoring**
3. **Set up automated scaling policies**
4. **Plan for 20-30% buffer** in budget

## Next Steps

1. **Deploy the system** using the provided configuration
2. **Monitor costs** for the first month
3. **Optimize based on usage patterns**
4. **Set up proper alerts and monitoring**

---

_Note: Costs are estimates based on Google Cloud pricing as of 2024. Actual costs may vary based on usage patterns, data transfer, and regional pricing differences._

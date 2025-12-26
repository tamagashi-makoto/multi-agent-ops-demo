# IntelliFlow AI Platform - FAQ

## Implementation

### Q: How long does implementation take?

A: Standard implementation takes 2-4 weeks, depending on your environment and requirements.
- Starter Plan: 1-2 weeks
- Professional Plan: 2-3 weeks
- Enterprise Plan: 4-8 weeks (including customization)

### Q: Can I use it on-premise?

A: Yes, the Enterprise Plan supports on-premise deployment. It can be smoothly deployed in Kubernetes environments.

### Q: Is integration with existing systems possible?

A: We provide REST and gRPC API, allowing integration with most systems. Standard support is also provided for major data warehouses (Snowflake, BigQuery, Redshift).

---

## Technology

### Q: Which ML frameworks are supported?

A: The following frameworks are supported:
- TensorFlow / Keras
- PyTorch
- scikit-learn
- XGBoost / LightGBM
- ONNX models

### Q: What is the inference speed?

A: It depends on the model size and complexity, but standard models achieve <10ms latency. Using GPUs enables fast inference even for large models.

### Q: Is model version control supported?

A: Yes, all models are automatically version-controlled. You can rollback to any version or split traffic for A/B testing.

---

## Security

### Q: Is data encrypted?

A: Yes, all data is encrypted in transit (TLS 1.3) and at rest (AES-256).

### Q: Are you SOC2 and GDPR compliant?

A: Yes, we are SOC2 Type II certified and fully GDPR compliant. Detailed compliance reports are available upon request.

### Q: How is access control handled?

A: We use Role-Based Access Control (RBAC). We also support Single Sign-On (SSO) via SAML/OIDC.

---

## Support

### Q: What are the support hours?

A: It depends on the plan:
- Starter: Weekdays 9:00-18:00 (Email)
- Professional: Weekdays 9:00-21:00 (Email, Phone, Chat)
- Enterprise: 24/7 (Dedicated Engineer)

### Q: Is training provided?

A: Yes, we offer the following training options:
- Online self-learning (Free)
- Live webinars (Monthly, Free)
- On-site training (Paid Option)

---

## Technical Limitations

### Q: Is there a model size limit?

A: We support models up to 100GB by default. If you need more, custom support is available on the Enterprise Plan.

### Q: Is batch processing supported?

A: Yes, in addition to real-time inference, batch inference is supported. Large batch jobs are executed efficiently with distributed processing.


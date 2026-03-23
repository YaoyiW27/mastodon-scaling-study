# Experiment 2 — Minimal Federation Validation

## Objective
Validate whether the Tiny Mastodon instance deployed on EC2 could participate in a minimal cross-instance federation workflow after upgrading the deployment from direct HTTP on port 3000 to an HTTPS + Nginx reverse-proxy setup.

## Environment
- **Instance A (Yaoyi):** `https://a.mastodon-yaoyi.online`
- **Instance B (Yehe):** `https://mastodon-yehe.click`

## Background
Federation did not work in the initial Tiny Mastodon deployment when Instance A was exposed directly over `http://a.mastodon-yaoyi.online:3000`.

At that stage:
- the instance itself was reachable in a browser,
- single-instance load testing was possible,
- but cross-instance account discovery was unreliable.

A likely reason was that the deployment did not yet match a standard Mastodon production setup. Instance A was missing:
- HTTPS on port 443,
- a valid SSL certificate,
- and Nginx-based reverse proxy routing.

To address this, the deployment was upgraded by:
- installing Nginx and Certbot,
- obtaining a valid Let's Encrypt certificate,
- configuring HTTPS for `a.mastodon-yaoyi.online`,
- and proxying traffic from Nginx to the Mastodon web service running on `127.0.0.1:3000`.

## Federation Validation Steps

### 1. Remote Account Discovery
After enabling HTTPS, Yaoyi was able to access Yehe’s remote profile page and interact using Mastodon’s federated follow flow.

### 2. Mutual Follow
A cross-instance mutual follow relationship was successfully established between:
- `@yaoyi@a.mastodon-yaoyi.online`
- `@admin@mastodon-yehe.click`

This confirmed that the two instances could discover each other and exchange follow relationships correctly.

### 3. Remote Post Visibility
A public test post from Yehe’s instance was successfully displayed on Yaoyi’s instance.

This confirmed that:
- the remote account timeline could be fetched,
- and at least basic post federation was functioning.

### 4. Remote Like / Favorite Notification
A favorite interaction from Yehe’s instance was received by Yaoyi’s instance as a notification.

This confirmed that remote interaction events were also propagating across instances.

## Results Summary

| Federation Check | Result |
|---|---|
| Remote account discovery | Success |
| Mutual follow | Success |
| Remote public post visibility | Success |
| Remote like / favorite notification | Success |

## Interpretation
The federation experiment shows that the Tiny Mastodon deployment became federation-capable only after it was upgraded to a more production-like configuration.

The critical change was not application logic, but deployment architecture:
- direct HTTP on port 3000 was sufficient for local functionality and single-instance load testing,
- but HTTPS + Nginx reverse proxy were required to make the instance discoverable and usable in a federated workflow.

This result is important because it demonstrates that federation readiness depends not only on Mastodon itself, but also on correct deployment of:
- domain routing,
- SSL/TLS,
- and reverse proxy behavior.

## Limitations
The federation test involved only two instances and a very small number of users. As a result, it validates federation functionality, but not federation performance at scale. In particular, this setup is insufficient to evaluate fan-out behavior, queue buildup, or delivery latency under broader multi-instance activity.

The experiment confirmed:
- remote account discovery,
- mutual follow,
- post visibility,
- and favorite notification propagation.

However, the following were not yet systematically evaluated:
- reply propagation,
- boost/reblog propagation,
- end-to-end delivery latency with repeated trials,
- queue delay under load,
- and federation behavior under concurrent traffic.

## Conclusion
A minimal federation workflow was successfully validated between Yaoyi’s Tiny Mastodon EC2 deployment and Yehe’s instance after HTTPS and Nginx reverse proxy were added.

This indicates that the EC2 + Docker Compose deployment path is not only sufficient for single-instance bottleneck experiments, but also capable of supporting basic inter-instance federation when configured with a production-style HTTPS endpoint.
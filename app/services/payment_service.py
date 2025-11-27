"""
Service de gestion des paiements mobile money.
Intègre les APIs Orange Money, MTN MoMo, Wave, etc.
"""

import httpx
from datetime import datetime
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from app.config import settings
from app.core.logging import logger, log_payment_event
from app.models.payment import Payment, PaymentMethod, PaymentStatus


class MobileMoneyProvider(ABC):
    """Interface abstraite pour les opérateurs mobile money."""
    
    @abstractmethod
    async def initiate_payment(
        self,
        amount: float,
        phone_number: str,
        reference: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """Initie un paiement."""
        pass
    
    @abstractmethod
    async def check_status(self, reference: str) -> Dict[str, Any]:
        """Vérifie le statut d'une transaction."""
        pass
    
    @abstractmethod
    async def refund(self, reference: str, amount: float) -> Dict[str, Any]:
        """Effectue un remboursement."""
        pass


class OrangeMoneyProvider(MobileMoneyProvider):
    """
    Implémentation pour Orange Money.
    Documentation: https://developer.orange.com/apis/om-webpay/overview
    """
    
    def __init__(self):
        self.api_key = settings.ORANGE_MONEY_API_KEY
        self.api_secret = settings.ORANGE_MONEY_API_SECRET
        self.callback_url = settings.ORANGE_MONEY_CALLBACK_URL
        self.base_url = "https://api.orange.com/orange-money-webpay"
        self.access_token = None
    
    async def _get_access_token(self) -> str:
        """Obtient un token d'accès OAuth."""
        if self.access_token:
            return self.access_token
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.orange.com/oauth/v3/token",
                headers={
                    "Authorization": f"Basic {self.api_key}:{self.api_secret}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data["access_token"]
                return self.access_token
            
            raise Exception(f"Erreur d'authentification Orange: {response.text}")
    
    async def initiate_payment(
        self,
        amount: float,
        phone_number: str,
        reference: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Initie un paiement Orange Money.
        
        Args:
            amount: Montant en FCFA
            phone_number: Numéro de téléphone du client
            reference: Référence unique de la transaction
            description: Description du paiement
            
        Returns:
            Réponse de l'API avec l'URL de paiement
        """
        logger.info(f"Initiation paiement Orange Money: {reference} - {amount} FCFA")
        
        try:
            token = await self._get_access_token()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v1/webpayment",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "merchant_key": self.api_key,
                        "currency": "OUV",  # Code devise Orange
                        "order_id": reference,
                        "amount": amount,
                        "return_url": self.callback_url,
                        "cancel_url": self.callback_url,
                        "notif_url": self.callback_url,
                        "lang": "fr",
                        "reference": description,
                    },
                )
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    log_payment_event(
                        event_type="initiation_success",
                        payment_id=reference,
                        amount=amount,
                        status="pending",
                        operator="orange_money",
                        details={"payment_url": data.get("payment_url")},
                    )
                    return {
                        "success": True,
                        "payment_url": data.get("payment_url"),
                        "pay_token": data.get("pay_token"),
                        "notif_token": data.get("notif_token"),
                    }
                
                logger.error(f"Erreur Orange Money: {response.text}")
                return {
                    "success": False,
                    "error": response.text,
                }
                
        except Exception as e:
            logger.error(f"Exception Orange Money: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def check_status(self, reference: str) -> Dict[str, Any]:
        """Vérifie le statut d'une transaction Orange Money."""
        try:
            token = await self._get_access_token()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/webpayment/{reference}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                
                if response.status_code == 200:
                    return response.json()
                
                return {"error": response.text}
                
        except Exception as e:
            return {"error": str(e)}
    
    async def refund(self, reference: str, amount: float) -> Dict[str, Any]:
        """Effectue un remboursement Orange Money."""
        # TODO: Implémenter le remboursement
        logger.warning(f"Remboursement non implémenté: {reference}")
        return {"success": False, "error": "Not implemented"}


class MTNMoMoProvider(MobileMoneyProvider):
    """
    Implémentation pour MTN Mobile Money.
    Documentation: https://momodeveloper.mtn.com/
    """
    
    def __init__(self):
        self.api_key = settings.MTN_MOMO_API_KEY
        self.api_secret = settings.MTN_MOMO_API_SECRET
        self.callback_url = settings.MTN_MOMO_CALLBACK_URL
        self.base_url = "https://sandbox.momodeveloper.mtn.com"  # Sandbox URL
    
    async def initiate_payment(
        self,
        amount: float,
        phone_number: str,
        reference: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """Initie un paiement MTN MoMo."""
        logger.info(f"Initiation paiement MTN MoMo: {reference} - {amount} FCFA")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/collection/v1_0/requesttopay",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "X-Reference-Id": reference,
                        "X-Target-Environment": "sandbox",
                        "Content-Type": "application/json",
                        "Ocp-Apim-Subscription-Key": self.api_secret,
                    },
                    json={
                        "amount": str(amount),
                        "currency": "XOF",
                        "externalId": reference,
                        "payer": {
                            "partyIdType": "MSISDN",
                            "partyId": phone_number,
                        },
                        "payerMessage": description,
                        "payeeNote": f"Kobiri - {description}",
                    },
                )
                
                if response.status_code in [200, 201, 202]:
                    log_payment_event(
                        event_type="initiation_success",
                        payment_id=reference,
                        amount=amount,
                        status="pending",
                        operator="mtn_momo",
                    )
                    return {
                        "success": True,
                        "reference": reference,
                    }
                
                logger.error(f"Erreur MTN MoMo: {response.text}")
                return {
                    "success": False,
                    "error": response.text,
                }
                
        except Exception as e:
            logger.error(f"Exception MTN MoMo: {e}")
            return {"success": False, "error": str(e)}
    
    async def check_status(self, reference: str) -> Dict[str, Any]:
        """Vérifie le statut d'une transaction MTN MoMo."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/collection/v1_0/requesttopay/{reference}",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "X-Target-Environment": "sandbox",
                        "Ocp-Apim-Subscription-Key": self.api_secret,
                    },
                )
                
                if response.status_code == 200:
                    return response.json()
                
                return {"error": response.text}
                
        except Exception as e:
            return {"error": str(e)}
    
    async def refund(self, reference: str, amount: float) -> Dict[str, Any]:
        """Effectue un remboursement MTN MoMo."""
        logger.warning(f"Remboursement MTN MoMo non implémenté: {reference}")
        return {"success": False, "error": "Not implemented"}


class WaveProvider(MobileMoneyProvider):
    """
    Implémentation pour Wave.
    Documentation: https://docs.wave.com/
    """
    
    def __init__(self):
        self.api_key = settings.WAVE_API_KEY
        self.api_secret = settings.WAVE_API_SECRET
        self.callback_url = settings.WAVE_CALLBACK_URL
        self.base_url = "https://api.wave.com"
    
    async def initiate_payment(
        self,
        amount: float,
        phone_number: str,
        reference: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """Initie un paiement Wave."""
        logger.info(f"Initiation paiement Wave: {reference} - {amount} FCFA")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/v1/checkout/sessions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "amount": str(int(amount)),
                        "currency": "XOF",
                        "error_url": self.callback_url,
                        "success_url": self.callback_url,
                        "client_reference": reference,
                    },
                )
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    log_payment_event(
                        event_type="initiation_success",
                        payment_id=reference,
                        amount=amount,
                        status="pending",
                        operator="wave",
                        details={"checkout_url": data.get("wave_launch_url")},
                    )
                    return {
                        "success": True,
                        "checkout_url": data.get("wave_launch_url"),
                        "checkout_id": data.get("id"),
                    }
                
                logger.error(f"Erreur Wave: {response.text}")
                return {
                    "success": False,
                    "error": response.text,
                }
                
        except Exception as e:
            logger.error(f"Exception Wave: {e}")
            return {"success": False, "error": str(e)}
    
    async def check_status(self, reference: str) -> Dict[str, Any]:
        """Vérifie le statut d'une transaction Wave."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/v1/checkout/sessions/{reference}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                
                if response.status_code == 200:
                    return response.json()
                
                return {"error": response.text}
                
        except Exception as e:
            return {"error": str(e)}
    
    async def refund(self, reference: str, amount: float) -> Dict[str, Any]:
        """Effectue un remboursement Wave."""
        logger.warning(f"Remboursement Wave non implémenté: {reference}")
        return {"success": False, "error": "Not implemented"}


class PaymentService:
    """
    Service principal de gestion des paiements.
    Orchestre les différents providers mobile money.
    """
    
    def __init__(self):
        self.providers = {
            "orange_money": OrangeMoneyProvider(),
            "mtn_momo": MTNMoMoProvider(),
            "wave": WaveProvider(),
        }
    
    def get_provider(self, method: PaymentMethod) -> Optional[MobileMoneyProvider]:
        """Retourne le provider pour une méthode de paiement."""
        return self.providers.get(method)
    
    async def initiate_payment(
        self,
        payment: Payment,
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Initie un paiement mobile money.
        
        Args:
            payment: Instance du paiement
            description: Description du paiement
            
        Returns:
            Résultat de l'initiation
        """
        provider = self.get_provider(payment.method)
        
        if not provider:
            logger.warning(f"Provider non supporté: {payment.method}")
            return {
                "success": False,
                "error": f"Méthode de paiement non supportée: {payment.method}",
            }
        
        return await provider.initiate_payment(
            amount=float(payment.amount) + float(payment.penalty_amount),
            phone_number=payment.phone_number,
            reference=payment.operator_reference,
            description=description,
        )
    
    async def check_payment_status(
        self,
        payment: Payment,
    ) -> Dict[str, Any]:
        """Vérifie le statut d'un paiement."""
        provider = self.get_provider(payment.method)
        
        if not provider:
            return {"error": "Provider non supporté"}
        
        return await provider.check_status(payment.operator_reference)
    
    async def process_callback(
        self,
        operator: str,
        callback_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Traite un callback d'opérateur.
        
        Args:
            operator: Nom de l'opérateur
            callback_data: Données du callback
            
        Returns:
            Résultat du traitement
        """
        logger.info(f"Traitement callback {operator}: {callback_data}")
        
        # Le traitement réel est fait dans les routes de callback
        # Cette méthode peut être utilisée pour des traitements communs
        
        return {
            "processed": True,
            "operator": operator,
        }


# Instance singleton du service
payment_service = PaymentService()


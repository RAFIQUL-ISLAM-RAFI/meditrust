"""Compatibility imports for the already deployed 0001/0002 migrations."""
from accounts.models import MediTrustUserManager, User
from medicines.models import Batch, Medicine, MedicineUnit, new_code
from tracking.models import OwnershipTransfer, Sale, VerificationLog

__all__ = ['MediTrustUserManager', 'User', 'Batch', 'Medicine', 'MedicineUnit',
           'OwnershipTransfer', 'Sale', 'VerificationLog', 'new_code']

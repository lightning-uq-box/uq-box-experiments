"""SKIPPD Datamodule."""

from typing import Any

import torch
from torch import Tensor
from torch.utils.data import DataLoader, random_split
from torchgeo.datamodules import SKIPPDDataModule

from skippd_ds import MySKIPPDDataset


class MySKIPPDDataModule(SKIPPDDataModule):
    """LightningDataModule implementation for the SKIPP'D dataset.

    Adds calibration dataset.
    """

    def __init__(
        self,
        batch_size: int = 64,
        num_workers: int = 0,
        val_split_pct: float = 0.2,
        **kwargs: Any,
    ) -> None:
        """Initialize a new SKIPPDDataModule instance.

        Args:
            batch_size: Size of each mini-batch.
            num_workers: Number of workers for parallel data loading.
            val_split_pct: Percentage of the dataset to use as a validation set.
            **kwargs: Additional keyword arguments passed to
                :class:`~torchgeo.datasets.SKIPPD`.
        """
        super().__init__(batch_size, num_workers, val_split_pct, **kwargs)

        self.target_mean = torch.Tensor([13.39907])
        self.target_std = torch.Tensor([7.67469])

        self.task = "regression"

    def setup(self, stage: str) -> None:
        """Set up datasets.

        Args:
            stage: Either 'fit', 'validate', 'test', or 'predict'.
        """
        if stage in ["fit", "validate"]:
            self.dataset = MySKIPPDDataset(split="trainval", **self.kwargs)

            # take 10 % of val_split data as calib_split
            calib_split_pct, val_split_pct = (
                0.1 * self.val_split_pct,
                0.9 * self.val_split_pct,
            )
            generator = torch.Generator().manual_seed(0)
            self.train_dataset, self.val_dataset, self.calibration_dataset = (
                random_split(
                    self.dataset,
                    [1 - self.val_split_pct, val_split_pct, calib_split_pct],
                    generator,
                )
            )
        if stage in ["test"]:
            self.test_dataset = MySKIPPDDataset(split="test", **self.kwargs)

    def calibration_dataloader(self) -> torch.utils.data.DataLoader:
        """Return a dataloader for the calibration dataset."""
        return DataLoader(
            self.calibration_dataset,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            collate_fn=self.collate_fn,
            shuffle=False,
        )

    def on_after_batch_transfer(
        self, batch: dict[str, Tensor], dataloader_idx: int
    ) -> dict[str, Tensor]:
        """Apply batch augmentations to the batch after it is transferred to the device.

        Args:
            batch: A batch of data that needs to be altered or augmented.
            dataloader_idx: The index of the dataloader to which the batch belongs.

        Returns:
            A batch of data.
        """
        new_batch = {
            "input": batch["input"].float(),
            "target": (
                batch["target"].float() - self.target_mean.to(batch["target"].device)
            )
            / self.target_std.to(batch["target"].device),
        }

        # add back all other keys
        for key, value in batch.items():
            if key not in ["input", "target"]:
                new_batch[key] = value
        return new_batch
